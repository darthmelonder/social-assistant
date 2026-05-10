from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.draft import Draft
from app.models.enums import DraftStatus, JobStatus, JobType, PriorityLevel
from app.models.message import Message
from app.models.sync_job import SyncJob
from app.models.thread import Thread
from app.models.thread_analysis import ThreadAnalysis
from app.models.user import User
from app.schemas.thread import (
    AnalysisOut,
    DraftOut,
    MessageOut,
    ThreadDetail,
    ThreadListResponse,
    ThreadPriorityPatch,
    ThreadSummary,
)

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    priority: str | None = Query(default=None),
    connection_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    after_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Priority inbox — paginated thread list with analysis data.

    Cursor-based: pass after_id (the UUID of the last thread received)
    to fetch the next page. next_cursor=null means no more pages.
    """
    stmt = (
        select(Thread)
        .where(
            Thread.user_id == current_user.id,
            Thread.deleted_at.is_(None),
            Thread.is_in_inbox.is_(True),
        )
        .order_by(Thread.last_message_at.desc().nulls_last(), Thread.id.desc())
    )

    if connection_id:
        stmt = stmt.where(Thread.connection_id == connection_id)

    # Priority filter via subquery — keeps pagination correct
    if priority:
        try:
            p_enum = PriorityLevel(priority)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority!r}")
        analysis_subq = (
            select(ThreadAnalysis.thread_id)
            .where(
                ThreadAnalysis.is_current.is_(True),
                ThreadAnalysis.priority == p_enum,
            )
            .scalar_subquery()
        )
        stmt = stmt.where(Thread.id.in_(analysis_subq))

    # Keyset cursor: (last_message_at DESC, id DESC)
    if after_id:
        cursor_result = await db.execute(
            select(Thread.last_message_at, Thread.id).where(Thread.id == after_id)
        )
        cursor_row = cursor_result.first()
        if cursor_row:
            ts, cid = cursor_row
            stmt = stmt.where(
                or_(
                    Thread.last_message_at < ts,
                    and_(Thread.last_message_at == ts, Thread.id < cid),
                )
            )

    result = await db.execute(stmt.limit(limit + 1))
    threads = list(result.scalars().all())

    has_more = len(threads) > limit
    threads = threads[:limit]
    next_cursor = str(threads[-1].id) if has_more and threads else None

    if not threads:
        return ThreadListResponse(threads=[], next_cursor=None)

    thread_ids = [t.id for t in threads]

    # Batch-load analyses and pending drafts
    analyses_result = await db.execute(
        select(ThreadAnalysis).where(
            ThreadAnalysis.thread_id.in_(thread_ids),
            ThreadAnalysis.is_current.is_(True),
        )
    )
    analyses = {a.thread_id: a for a in analyses_result.scalars().all()}

    drafts_result = await db.execute(
        select(Draft).where(
            Draft.thread_id.in_(thread_ids),
            Draft.status == DraftStatus.PENDING_REVIEW,
        )
    )
    drafts = {d.thread_id: d for d in drafts_result.scalars().all()}

    summaries = [_to_summary(t, analyses.get(t.id), drafts.get(t.id)) for t in threads]
    return ThreadListResponse(threads=summaries, next_cursor=next_cursor)


@router.get("/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Thread detail: messages, current analysis, and latest pending draft."""
    thread = await _get_thread_or_404(db, thread_id, current_user.id)

    msgs_result = await db.execute(
        select(Message)
        .where(Message.thread_id == thread.id, Message.deleted_at.is_(None))
        .order_by(Message.internal_date)
    )
    messages = list(msgs_result.scalars().all())

    analysis_result = await db.execute(
        select(ThreadAnalysis).where(
            ThreadAnalysis.thread_id == thread.id,
            ThreadAnalysis.is_current.is_(True),
        )
    )
    analysis = analysis_result.scalar_one_or_none()

    draft_result = await db.execute(
        select(Draft).where(
            Draft.thread_id == thread.id,
            Draft.status == DraftStatus.PENDING_REVIEW,
        ).order_by(Draft.generated_at.desc()).limit(1)
    )
    draft = draft_result.scalar_one_or_none()

    return ThreadDetail(
        id=thread.id,
        subject=thread.subject,
        snippet=thread.snippet,
        last_message_at=thread.last_message_at,
        is_unread=thread.is_unread,
        participants=thread.participants or [],
        messages=[MessageOut.model_validate(m) for m in messages],
        analysis=AnalysisOut.model_validate(analysis) if analysis else None,
        draft=DraftOut.model_validate(draft) if draft else None,
    )


@router.post("/{thread_id}/retriage", status_code=status.HTTP_202_ACCEPTED)
async def retriage_thread(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request re-triage of a thread (e.g. after new messages arrive)."""
    thread = await _get_thread_or_404(db, thread_id, current_user.id)

    job = SyncJob(
        id=uuid.uuid4(),
        user_id=current_user.id,
        connection_id=thread.connection_id,
        job_type=JobType.TRIAGE,
        status=JobStatus.QUEUED,
        triggered_by="user",
        job_metadata={"thread_id": str(thread.id)},
    )
    db.add(job)
    await db.commit()
    return {"job_id": str(job.id), "message": "Retriage queued"}


@router.patch("/{thread_id}")
async def patch_thread(
    thread_id: uuid.UUID,
    body: ThreadPriorityPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually override a thread's priority label."""
    thread = await _get_thread_or_404(db, thread_id, current_user.id)

    analysis_result = await db.execute(
        select(ThreadAnalysis).where(
            ThreadAnalysis.thread_id == thread.id,
            ThreadAnalysis.is_current.is_(True),
        )
    )
    analysis = analysis_result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="No analysis found for thread")

    try:
        analysis.priority = PriorityLevel(body.priority_override)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {body.priority_override!r}")

    await db.commit()
    return {"id": str(thread.id), "priority_override": body.priority_override}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_thread_or_404(
    db: AsyncSession, thread_id: uuid.UUID, user_id: uuid.UUID
) -> Thread:
    result = await db.execute(
        select(Thread).where(
            Thread.id == thread_id,
            Thread.user_id == user_id,  # row-level scoping
            Thread.deleted_at.is_(None),
        )
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread


def _to_summary(thread: Thread, analysis: ThreadAnalysis | None, draft: Draft | None) -> ThreadSummary:
    return ThreadSummary(
        id=thread.id,
        subject=thread.subject,
        snippet=thread.snippet,
        last_message_at=thread.last_message_at,
        is_unread=thread.is_unread,
        participants=thread.participants or [],
        priority=analysis.priority.value if analysis else None,
        summary=analysis.summary if analysis else None,
        action_items=analysis.action_items if analysis else [],
        requires_reply=analysis.requires_reply if analysis else False,
        draft_status=draft.status.value if draft else None,
    )
