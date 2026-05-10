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
from app.models.user_profile import UserProfile
from app.schemas.profile import JobOut, ProfileOut

router = APIRouter(tags=["profile"])


@router.get("/api/v1/profile", response_model=ProfileOut)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's behavioral profile."""
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.user_id == current_user.id,
            UserProfile.is_current.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile built yet — connect Gmail and complete an initial sync first",
        )
    return profile


@router.post("/api/v1/profile/rebuild", status_code=status.HTTP_202_ACCEPTED)
async def rebuild_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a profile rebuild from the current sent-mail corpus."""
    conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.user_id == current_user.id,
            PlatformConnection.status == ConnectionStatus.ACTIVE,
        ).limit(1)
    )
    conn = conn_result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active platform connection found",
        )

    job = SyncJob(
        id=uuid.uuid4(),
        user_id=current_user.id,
        connection_id=conn.id,
        job_type=JobType.PROFILE_REBUILD,
        status=JobStatus.QUEUED,
        triggered_by="user",
    )
    db.add(job)
    await db.commit()
    return {"job_id": str(job.id)}


@router.get("/api/v1/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll the status of a background job."""
    result = await db.execute(
        select(SyncJob).where(
            SyncJob.id == job_id,
            SyncJob.user_id == current_user.id,  # row-level scoping
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
