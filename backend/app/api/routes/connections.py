from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.enums import ConnectionStatus, JobStatus, JobType
from app.models.platform_connection import PlatformConnection
from app.models.sync_job import SyncJob
from app.models.user import User
from app.schemas.connection import ConnectionOut

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


@router.get("", response_model=list[ConnectionOut])
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active platform connections for the current user."""
    result = await db.execute(
        select(PlatformConnection)
        .where(
            PlatformConnection.user_id == current_user.id,
            PlatformConnection.status != ConnectionStatus.REVOKED,
        )
        .order_by(PlatformConnection.created_at)
    )
    return result.scalars().all()


@router.get("/{connection_id}", response_model=ConnectionOut)
async def get_connection(
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await _get_connection_or_404(db, connection_id, current_user.id)
    return conn


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a platform connection. Tokens are marked revoked; data is kept."""
    conn = await _get_connection_or_404(db, connection_id, current_user.id)
    conn.status = ConnectionStatus.REVOKED
    conn.encrypted_access_token = b""
    conn.encrypted_refresh_token = None
    await db.commit()


@router.post("/{connection_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enqueue a manual incremental sync for a connection."""
    conn = await _get_connection_or_404(db, connection_id, current_user.id)

    job = SyncJob(
        id=uuid.uuid4(),
        user_id=current_user.id,
        connection_id=conn.id,
        job_type=JobType.INCREMENTAL_SYNC,
        status=JobStatus.QUEUED,
        triggered_by="user",
    )
    db.add(job)
    await db.commit()
    return {"job_id": str(job.id)}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_connection_or_404(
    db: AsyncSession, connection_id: uuid.UUID, user_id: uuid.UUID
) -> PlatformConnection:
    result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.id == connection_id,
            PlatformConnection.user_id == user_id,  # row-level scoping
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return conn
