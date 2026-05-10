"""Draft Worker — ARQ job that generates a reply draft in the user's voice.

Triggered by the Triage Worker when a thread is classified as urgent or
important with requires_reply=True. One Claude API call per draft request.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draft import Draft
from app.models.enums import DraftStatus
from app.models.message import Message
from app.models.thread import Thread
from app.models.thread_analysis import ThreadAnalysis
from app.models.user_profile import UserProfile
from app.workers.draft.service import DraftResult, generate_draft

_EXAMPLE_MESSAGES_LIMIT = 5   # sent emails injected into the voice context


# ── Core logic ────────────────────────────────────────────────────────────────

async def run_draft_generate(
    db: AsyncSession,
    thread: Thread,
    messages: list[Message],
    analysis: ThreadAnalysis,
    profile: UserProfile | None,
    example_messages: list[Message],
) -> Draft:
    """Generate a draft reply and persist it with status=pending_review."""
    action_items: list[dict] = list(analysis.action_items or [])

    result: DraftResult = await generate_draft(
        thread, messages, action_items,
        profile=profile,
        example_messages=example_messages,
    )

    draft = Draft(
        id=uuid.uuid4(),
        thread_id=thread.id,
        user_id=thread.user_id,
        analysis_id=analysis.id,
        subject_line=result.subject_line,
        body_plain=result.body_plain,
        body_html=result.body_html,
        tone_used=result.tone_used,
        status=DraftStatus.PENDING_REVIEW,
        model_id=result.model_id,
        model_version=result.model_version,
        prompt_template_hash=result.prompt_template_hash,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_write_tokens=result.cache_write_tokens,
    )
    db.add(draft)
    await db.commit()
    return draft


# ── ARQ entry point ───────────────────────────────────────────────────────────

async def draft_generate_job(ctx: dict, *, thread_id: str, analysis_id: str) -> None:
    """ARQ job: generate a draft reply for one thread."""
    session_factory = ctx["session_factory"]
    async with session_factory() as db:
        context = await _load_draft_context(db, uuid.UUID(thread_id), uuid.UUID(analysis_id))
        if context is None:
            return  # thread or analysis was deleted before the job ran
        thread, messages, analysis, profile, examples = context
        await run_draft_generate(db, thread, messages, analysis, profile, examples)


async def _load_draft_context(
    db: AsyncSession,
    thread_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> tuple[Thread, list[Message], ThreadAnalysis, UserProfile | None, list[Message]] | None:
    """Load everything run_draft_generate needs in four DB queries."""
    thread_result = await db.execute(select(Thread).where(Thread.id == thread_id))
    thread = thread_result.scalar_one_or_none()
    if thread is None:
        return None

    analysis_result = await db.execute(
        select(ThreadAnalysis).where(ThreadAnalysis.id == analysis_id)
    )
    analysis = analysis_result.scalar_one_or_none()
    if analysis is None:
        return None

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

    examples_result = await db.execute(
        select(Message)
        .where(
            Message.user_id == thread.user_id,
            Message.is_sent_by_user.is_(True),
            Message.deleted_at.is_(None),
        )
        .order_by(Message.internal_date.desc())
        .limit(_EXAMPLE_MESSAGES_LIMIT)
    )
    example_messages = list(examples_result.scalars().all())

    return thread, messages, analysis, profile, example_messages
