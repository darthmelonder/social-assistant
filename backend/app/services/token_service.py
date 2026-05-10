"""Token decryption and refresh service for platform connections.

Workers call get_valid_access_token() before every API call. If the stored
token is within REFRESH_BUFFER_MINUTES of expiry, it refreshes automatically,
re-encrypts the new tokens, and persists the update.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import PlatformConnector
from app.models.platform_connection import PlatformConnection
from app.services.encryption import EncryptedToken, get_encryption_service

REFRESH_BUFFER_MINUTES = 5


class TokenRefreshError(Exception):
    """Raised when a token is expired and cannot be refreshed."""


def _utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware in UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def decrypt_access_token(conn: PlatformConnection) -> str:
    """Decrypt and return the access token stored on a platform connection.

    Does NOT check expiry — use get_valid_access_token() for that.
    """
    enc_svc = get_encryption_service()
    token = EncryptedToken(
        ciphertext=conn.encrypted_access_token,
        iv=conn.token_iv,
        tag=conn.token_tag,
        key_id=conn.token_key_id,
    )
    return enc_svc.decrypt(token)


async def get_valid_access_token(
    conn: PlatformConnection,
    connector: PlatformConnector,
    db: AsyncSession,
) -> str:
    """Return a valid decrypted access token, refreshing via the connector if needed.

    Refreshes when the token is within REFRESH_BUFFER_MINUTES of expiry so
    workers never make API calls with a token that will expire mid-request.
    New tokens are re-encrypted and committed to DB before returning.
    """
    now = datetime.now(timezone.utc)
    expires_at = _utc(conn.token_expires_at)

    if expires_at > now + timedelta(minutes=REFRESH_BUFFER_MINUTES):
        return decrypt_access_token(conn)

    # Token expired or expiring — refresh it
    if not conn.encrypted_refresh_token:
        raise TokenRefreshError(
            f"Connection {conn.id}: access token expired and no refresh token is stored"
        )

    enc_svc = get_encryption_service()
    enc_refresh = EncryptedToken.from_blob(
        conn.encrypted_refresh_token, key_id=conn.token_key_id
    )
    refresh_token_str = enc_svc.decrypt(enc_refresh)

    try:
        new_bundle = await connector.refresh_access_token(refresh_token_str)
    except Exception as exc:
        raise TokenRefreshError(
            f"Connection {conn.id}: platform token refresh failed"
        ) from exc

    # Re-encrypt and persist the new access token
    new_enc = enc_svc.encrypt(new_bundle.access_token)
    conn.encrypted_access_token = new_enc.ciphertext
    conn.token_iv = new_enc.iv
    conn.token_tag = new_enc.tag
    conn.token_key_id = new_enc.key_id
    conn.token_expires_at = new_bundle.expires_at

    # Persist a new refresh token only if Google actually rotated it
    if new_bundle.refresh_token and new_bundle.refresh_token != refresh_token_str:
        conn.encrypted_refresh_token = enc_svc.encrypt(new_bundle.refresh_token).to_blob()

    await db.commit()
    return new_bundle.access_token
