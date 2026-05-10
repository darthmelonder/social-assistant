"""Sent-mail sampler for profile building.

Fetches the user's sent messages from the DB and returns a stratified
sample spread across the last N months to avoid recency bias.
"""
from __future__ import annotations

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


@dataclass
class SentMessageSample:
    """Lightweight projection of a sent Message, ready for prompt formatting."""
    platform_message_id: str
    subject: str | None
    body_plain: str | None
    internal_date: datetime
    to_emails: list[str] = field(default_factory=list)
    word_count: int = 0  # precomputed so builder can average without re-parsing


async def fetch_sent_samples(
    db: AsyncSession,
    connection_id: uuid.UUID,
    user_id: uuid.UUID,
    max_total: int = 200,
    months_back: int = 12,
) -> list[SentMessageSample]:
    """Return up to max_total sent messages, stratified across the last months_back months.

    Stratification prevents the sample from being dominated by a recent burst
    of emails. Up to max_total // months_back messages are taken from each
    monthly bucket; the result is sorted oldest-first so the builder sees a
    chronological narrative.
    """
    date_from = datetime.now(timezone.utc) - timedelta(days=30 * months_back)

    result = await db.execute(
        select(Message)
        .where(
            Message.connection_id == connection_id,
            Message.user_id == user_id,
            Message.is_sent_by_user.is_(True),
            Message.deleted_at.is_(None),
            Message.internal_date >= date_from,
        )
        .order_by(Message.internal_date.desc())
        .limit(max_total * 3)  # fetch extra to allow stratification to thin it out
    )
    rows = result.scalars().all()

    samples = [
        SentMessageSample(
            platform_message_id=m.platform_message_id,
            subject=m.subject,
            body_plain=m.body_plain,
            internal_date=_ensure_utc(m.internal_date),
            to_emails=list(m.to_emails or []),
            word_count=len((m.body_plain or "").split()),
        )
        for m in rows
    ]

    return _stratify(samples, max_total=max_total, months_back=months_back)


def _stratify(
    samples: list[SentMessageSample],
    max_total: int,
    months_back: int,
) -> list[SentMessageSample]:
    """Spread samples evenly across monthly buckets, then sort oldest-first."""
    if not samples:
        return []

    per_bucket = max(1, math.ceil(max_total / months_back))
    now = datetime.now(timezone.utc)

    buckets: dict[int, list[SentMessageSample]] = defaultdict(list)
    for s in samples:
        age_months = (
            (now.year - s.internal_date.year) * 12
            + (now.month - s.internal_date.month)
        )
        bucket = min(age_months, months_back - 1)
        buckets[bucket].append(s)

    selected: list[SentMessageSample] = []
    for msgs in buckets.values():
        selected.extend(msgs[:per_bucket])

    selected.sort(key=lambda s: s.internal_date)
    return selected[:max_total]


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
