from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.draft import Draft
from app.models.enums import DraftStatus, JobStatus, JobType
from app.models.sync_job import SyncJob
from app.models.thread import Thread
from app.models.thread_analysis import ThreadAnalysis
from app.models.user import User
from app.schemas.draft import DraftListItem, DraftUpdateRequest

router = APIRouter(tags=["drafts"])


# ── /api/v1/threads/:thread_id/drafts ────────────────────────────────────────

@router.get("/api/v1/threads/{thread_id}/drafts", response_model=list[DraftListItem])
async def list_drafts(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all drafts for a thread, newest first (includes superseded)."""
    await _get_thread_or_404(db, thread_id, current_user.id)

    result = await db.execute(
        select(Draft)
        .where(Draft.thread_id == thread_id)
        .order_by(Draft.generated_at.desc())
    )
    return result.scalars().all()


@router.post("/api/v1/threads/{thread_id}/drafts", status_code=status.HTTP_202_ACCEPTED)
async def request_draft(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request generation of a new draft for a thread."""
    thread = await _get_thread_or_404(db, thread_id, current_user.id)

    analysis_result = await db.execute(
        select(ThreadAnalysis).where(
            ThreadAnalysis.thread_id == thread.id,
            ThreadAnalysis.is_current.is_(True),
        )
    )
    analysis = analysis_result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thread has not been triaged yet — triage must complete before draft generation",
        )

    job = SyncJob(
        id=uuid.uuid4(),
        user_id=current_user.id,
        connection_id=thread.connection_id,
        job_type=JobType.DRAFT_GENERATE,
        status=JobStatus.QUEUED,
        triggered_by="user",
        job_metadata={"thread_id": str(thread.id), "analysis_id": str(analysis.id)},
    )
    db.add(job)
    await db.commit()
    return {"job_id": str(job.id)}


# ── /api/v1/drafts/:id ────────────────────────────────────────────────────────

@router.patch("/api/v1/drafts/{draft_id}", response_model=DraftListItem)
async def update_draft(
    draft_id: uuid.UUID,
    body: DraftUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve, reject, or mark a draft as copied.

    Optionally include user_edited_body (if the user tweaked it before sending)
    and feedback_note (reason for rejection, for future draft quality analysis).
    """
    result = await db.execute(
        select(Draft).where(
            Draft.id == draft_id,
            Draft.user_id == current_user.id,  # row-level scoping
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    draft.status = DraftStatus(body.status)
    draft.reviewed_at = datetime.now(timezone.utc)
    if body.user_edited_body is not None:
        draft.user_edited_body = body.user_edited_body
    if body.feedback_note is not None:
        draft.feedback_note = body.feedback_note

    await db.commit()
    return draft


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_thread_or_404(
    db: AsyncSession, thread_id: uuid.UUID, user_id: uuid.UUID
) -> Thread:
    result = await db.execute(
        select(Thread).where(
            Thread.id == thread_id,
            Thread.user_id == user_id,
            Thread.deleted_at.is_(None),
        )
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread
