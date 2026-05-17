import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.models.enums import ConnectionStatus, JobStatus, JobType, PlatformType
from app.models.platform_connection import PlatformConnection
from app.models.sync_job import SyncJob
from app.models.user import User
from app.services.encryption import get_encryption_service
from app.services.google_oauth import GoogleOAuthError, get_google_oauth_service
from app.services.jwt_service import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_COOKIE_OPTS = dict(httponly=True, secure=True, samesite="lax")


@router.get("/google/authorize")
async def google_authorize():
    """Return the Google OAuth2 URL the client should redirect the user to."""
    state = secrets.token_urlsafe(32)
    url = get_google_oauth_service().get_authorize_url(state=state)
    return {"authorize_url": url, "state": state}


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
    redis: Any | None = Depends(get_redis),
):
    """Handle Google OAuth2 callback: exchange code, upsert user + connection, issue JWTs."""
    google_svc = get_google_oauth_service()
    try:
        token_bundle = await google_svc.exchange_code(code)
        user_info = await google_svc.get_user_info(token_bundle.access_token)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    now = datetime.now(timezone.utc)

    # ── Upsert User ───────────────────────────────────────────────────────────
    result = await db.execute(select(User).where(User.email == user_info.email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=user_info.email,
            display_name=user_info.name,
            avatar_url=user_info.picture,
            last_login_at=now,
        )
        db.add(user)
    else:
        user.display_name = user_info.name
        user.avatar_url = user_info.picture
        user.last_login_at = now

    await db.flush()  # ensures user.id is set before FK reference below

    # ── Encrypt Google tokens ─────────────────────────────────────────────────
    enc_svc = get_encryption_service()
    enc_access = enc_svc.encrypt(token_bundle.access_token)
    token_expires_at = now + timedelta(seconds=token_bundle.expires_in)
    granted_scopes = token_bundle.scope.split() if token_bundle.scope else []

    # ── Upsert PlatformConnection ─────────────────────────────────────────────
    result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.user_id == user.id,
            PlatformConnection.platform == PlatformType.GMAIL,
            PlatformConnection.platform_account_id == user_info.sub,
        )
    )
    conn = result.scalar_one_or_none()

    refresh_blob = (
        enc_svc.encrypt(token_bundle.refresh_token).to_blob()
        if token_bundle.refresh_token
        else None
    )

    is_new_connection = conn is None

    if conn is None:
        conn = PlatformConnection(
            id=uuid.uuid4(),
            user_id=user.id,
            platform=PlatformType.GMAIL,
            platform_account_id=user_info.sub,
            platform_email=user_info.email,
            encrypted_access_token=enc_access.ciphertext,
            encrypted_refresh_token=refresh_blob,
            token_iv=enc_access.iv,
            token_tag=enc_access.tag,
            token_key_id=enc_access.key_id,
            token_expires_at=token_expires_at,
            granted_scopes=granted_scopes,
            status=ConnectionStatus.ACTIVE,
        )
        db.add(conn)
    else:
        conn.encrypted_access_token = enc_access.ciphertext
        conn.token_iv = enc_access.iv
        conn.token_tag = enc_access.tag
        conn.token_key_id = enc_access.key_id
        conn.token_expires_at = token_expires_at
        conn.granted_scopes = granted_scopes
        conn.status = ConnectionStatus.ACTIVE
        conn.last_sync_error = None
        if refresh_blob:
            conn.encrypted_refresh_token = refresh_blob

    await db.commit()

    # Auto-enqueue full sync on first connect
    if is_new_connection and redis is not None:
        sync_job = SyncJob(
            id=uuid.uuid4(),
            user_id=user.id,
            connection_id=conn.id,
            job_type=JobType.FULL_SYNC,
            status=JobStatus.QUEUED,
            triggered_by="oauth_callback",
        )
        db.add(sync_job)
        await db.commit()
        await redis.enqueue_job(
            "full_sync_job",
            connection_id=str(conn.id),
            job_id=str(sync_job.id),
        )

    # ── Issue app JWTs ────────────────────────────────────────────────────────
    access_token = create_access_token(user.id)
    app_refresh = create_refresh_token(user.id)

    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
        },
    })
    response.set_cookie(
        key=_REFRESH_COOKIE, value=app_refresh,
        max_age=7 * 24 * 3600, **_COOKIE_OPTS,
    )
    return response


@router.post("/refresh")
async def refresh(refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE)):
    """Exchange a valid refresh cookie for a new access token."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )
    try:
        payload = decode_refresh_token(refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return {"access_token": create_access_token(payload.user_id), "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Clear the refresh token cookie."""
    response.delete_cookie(key=_REFRESH_COOKIE, **_COOKIE_OPTS)


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "avatar_url": current_user.avatar_url,
    }
