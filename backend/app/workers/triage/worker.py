"""Triage Worker — ARQ job that classifies and summarises a thread.

Triggered by the Ingestion Worker after each new or updated thread is
persisted. One Claude API call per thread per triage run.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PriorityLevel, SentimentType
from app.models.message import Message
from app.models.thread import Thread
from app.models.thread_analysis import ThreadAnalysis
from app.models.user_profile import UserProfile
from app.workers.triage.service import TriageResult, triage_thread


# ── Core logic (injected deps — fully testable) ───────────────────────────────

async def run_triage(
    db: AsyncSession,
    thread: Thread,
    messages: list[Message],
    profile: UserProfile | None,
) -> ThreadAnalysis | None:
    """Classify and summarise one thread.

    Returns the new ThreadAnalysis, or None if the thread content hasn't
    changed since the last analysis (source_message_hash matches — no-op).
    """
    if not messages:
        return None

    result: TriageResult = await triage_thread(thread, messages, profile)

    # Skip re-write when thread content is identical to last analysis
    existing_result = await db.execute(
        select(ThreadAnalysis).where(
            ThreadAnalysis.thread_id == thread.id,
            ThreadAnalysis.is_current.is_(True),
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing and existing.source_message_hash == result.source_message_hash:
        return None

    # Supersede the previous analysis
    await db.execute(
        update(ThreadAnalysis)
        .where(
            ThreadAnalysis.thread_id == thread.id,
            ThreadAnalysis.is_current.is_(True),
        )
        .values(is_current=False)
    )

    analysis = ThreadAnalysis(
        id=uuid.uuid4(),
        thread_id=thread.id,
        user_id=thread.user_id,
        priority=PriorityLevel(result.priority),
        priority_confidence=result.priority_confidence,
        summary=result.summary,
        action_items=result.action_items,
        requires_reply=result.requires_reply,
        sentiment=SentimentType(result.sentiment) if result.sentiment else None,
        source_message_ids=result.source_message_ids,
        source_message_hash=result.source_message_hash,
        model_id=result.model_id,
        model_version=result.model_version,
        prompt_template_hash=result.prompt_template_hash,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_write_tokens=result.cache_write_tokens,
        is_current=True,
    )
    db.add(analysis)
    await db.commit()
    return analysis


# ── ARQ entry point ───────────────────────────────────────────────────────────

async def triage_job(ctx: dict, *, thread_id: str) -> None:
    """ARQ job: triage one thread and — when warranted — enqueue draft generation."""
    session_factory = ctx["session_factory"]
    async with session_factory() as db:
        thread, messages, profile = await _load_triage_context(db, uuid.UUID(thread_id))
        if thread is None:
            return  # thread was deleted before job ran
        analysis = await run_triage(db, thread, messages, profile)

    # Enqueue draft generation when triage says a reply is needed
    if (
        analysis is not None
        and analysis.priority in (PriorityLevel.URGENT, PriorityLevel.IMPORTANT)
        and analysis.requires_reply
    ):
        redis = ctx.get("redis")
        if redis:
            await redis.enqueue_job(
                "draft_generate_job",
                thread_id=thread_id,
                analysis_id=str(analysis.id),
            )


async def _load_triage_context(
    db: AsyncSession,
    thread_id: uuid.UUID,
) -> tuple[Thread | None, list[Message], UserProfile | None]:
    """Load everything run_triage needs in three DB queries."""
    thread_result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = thread_result.scalar_one_or_none()
    if thread is None:
        return None, [], None

    msgs_result = await db.execute(
        select(Message)
        .where(Message.thread_id == thread.id, Message.deleted_at.is_(None))
        .order_by(Message.internal_date)
    )
    messages = list(msgs_result.scalars().all())

    profile_result = await db.execute(
        select(UserProfile).where(
            UserProfile.user_id == thread.user_id,
            UserProfile.is_current.is_(True),
        )
    )
    profile = profile_result.scalar_one_or_none()

    return thread, messages, profile
