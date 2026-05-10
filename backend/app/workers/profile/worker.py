"""Profile rebuild ARQ job.

Triggered after the initial full sync completes and thereafter whenever
≥10 new sent messages have been ingested. One Claude API call per rebuild.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_connection import PlatformConnection
from app.models.user_profile import UserProfile
from app.workers.profile.builder import build_profile
from app.workers.profile.sampler import fetch_sent_samples


async def run_profile_rebuild(
    db: AsyncSession,
    conn: PlatformConnection,
) -> UserProfile | None:
    """Core profile rebuild logic (injected deps — fully testable).

    Returns the newly created UserProfile, or None if the user has no sent
    messages to analyse yet (graceful no-op).
    """
    samples = await fetch_sent_samples(db, conn.id, conn.user_id)
    if not samples:
        return None

    result = await build_profile(samples)

    # Get current version so we can increment it
    existing_result = await db.execute(
        select(UserProfile).where(
            UserProfile.connection_id == conn.id,
            UserProfile.is_current.is_(True),
        )
    )
    existing = existing_result.scalar_one_or_none()
    next_version = (existing.profile_version + 1) if existing else 1

    # Mark previous profile as superseded
    await db.execute(
        update(UserProfile)
        .where(
            UserProfile.connection_id == conn.id,
            UserProfile.is_current.is_(True),
        )
        .values(is_current=False)
    )

    analyzed_dates = [s.internal_date.date() for s in samples]
    new_profile = UserProfile(
        id=uuid.uuid4(),
        user_id=conn.user_id,
        connection_id=conn.id,
        profile_version=next_version,
        is_current=True,
        voice_summary=result.voice_summary,
        tone_attributes=result.tone_attributes,
        attributes=result.attributes,
        messages_analyzed_count=result.messages_analyzed_count,
        analyzed_date_range_start=min(analyzed_dates),
        analyzed_date_range_end=max(analyzed_dates),
        model_id=result.model_id,
        model_version=result.model_version,
        prompt_template_hash=result.prompt_template_hash,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_write_tokens=result.cache_write_tokens,
    )
    db.add(new_profile)
    await db.commit()
    return new_profile


# ── ARQ entry point ───────────────────────────────────────────────────────────

async def profile_rebuild_job(ctx: dict, *, connection_id: str) -> None:
    """ARQ job: rebuild the behavioral profile for one platform connection."""
    from sqlalchemy import select as _select

    session_factory = ctx["session_factory"]
    async with session_factory() as db:
        result = await db.execute(
            _select(PlatformConnection).where(
                PlatformConnection.id == uuid.UUID(connection_id)
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None:
            return  # connection was deleted — nothing to do
        await run_profile_rebuild(db, conn)
