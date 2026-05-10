"""Unit tests for the sent-mail sampler."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers.profile.sampler import (
    SentMessageSample,
    _stratify,
    fetch_sent_samples,
)

CONN_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _sample(
    msg_id: str = "msg-1",
    days_ago: int = 0,
    body: str = "Hello world this is a test",
    subject: str = "Test",
) -> SentMessageSample:
    return SentMessageSample(
        platform_message_id=msg_id,
        subject=subject,
        body_plain=body,
        internal_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
        to_emails=["recipient@example.com"],
        word_count=len(body.split()),
    )


def _make_db_message(msg_id: str, days_ago: int, body: str = "Hello world") -> MagicMock:
    msg = MagicMock()
    msg.platform_message_id = msg_id
    msg.subject = "Test subject"
    msg.body_plain = body
    msg.internal_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
    msg.to_emails = ["to@example.com"]
    msg.is_sent_by_user = True
    msg.deleted_at = None
    return msg


def _mock_db(messages: list) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = messages
    result.scalars.return_value = scalars
    db.execute.return_value = result
    return db


# ── SentMessageSample ─────────────────────────────────────────────────────────

def test_sample_word_count():
    s = _sample(body="one two three four five")
    assert s.word_count == 5


def test_sample_empty_body_word_count():
    s = _sample(body="")
    assert s.word_count == 0


# ── _stratify ─────────────────────────────────────────────────────────────────

def test_stratify_empty_returns_empty():
    assert _stratify([], max_total=200, months_back=12) == []


def test_stratify_returns_at_most_max_total():
    samples = [_sample(f"msg-{i}", days_ago=i) for i in range(300)]
    result = _stratify(samples, max_total=200, months_back=12)
    assert len(result) <= 200


def test_stratify_result_sorted_oldest_first():
    # Mix old and recent messages
    samples = [_sample("new", days_ago=1), _sample("old", days_ago=300)]
    result = _stratify(samples, max_total=200, months_back=12)
    if len(result) >= 2:
        assert result[0].internal_date <= result[-1].internal_date


def test_stratify_spreads_across_months():
    # 60 messages in the last month, 60 from 6 months ago
    recent = [_sample(f"r{i}", days_ago=i) for i in range(60)]
    old = [_sample(f"o{i}", days_ago=180 + i) for i in range(60)]
    result = _stratify(recent + old, max_total=24, months_back=12)

    recent_ids = {s.platform_message_id for s in result if s.platform_message_id.startswith("r")}
    old_ids = {s.platform_message_id for s in result if s.platform_message_id.startswith("o")}

    # Both groups should be represented
    assert len(recent_ids) > 0
    assert len(old_ids) > 0


def test_stratify_small_input_returns_all():
    samples = [_sample(f"msg-{i}", days_ago=i * 10) for i in range(5)]
    result = _stratify(samples, max_total=200, months_back=12)
    assert len(result) == 5


def test_stratify_single_message():
    samples = [_sample("only", days_ago=30)]
    result = _stratify(samples, max_total=200, months_back=12)
    assert len(result) == 1
    assert result[0].platform_message_id == "only"


# ── fetch_sent_samples ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_sent_samples_queries_db():
    db = _mock_db([])
    await fetch_sent_samples(db, CONN_ID, USER_ID)
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_sent_samples_returns_samples():
    db_messages = [_make_db_message(f"msg-{i}", days_ago=i * 5) for i in range(10)]
    db = _mock_db(db_messages)

    result = await fetch_sent_samples(db, CONN_ID, USER_ID, max_total=200)

    assert len(result) == 10
    assert all(isinstance(s, SentMessageSample) for s in result)


@pytest.mark.asyncio
async def test_fetch_sent_samples_computes_word_count():
    msg = _make_db_message("msg-1", days_ago=5, body="one two three")
    db = _mock_db([msg])

    result = await fetch_sent_samples(db, CONN_ID, USER_ID)

    assert result[0].word_count == 3


@pytest.mark.asyncio
async def test_fetch_sent_samples_handles_none_body():
    msg = _make_db_message("msg-1", days_ago=5)
    msg.body_plain = None
    db = _mock_db([msg])

    result = await fetch_sent_samples(db, CONN_ID, USER_ID)

    assert result[0].word_count == 0
    assert result[0].body_plain is None


@pytest.mark.asyncio
async def test_fetch_sent_samples_returns_empty_for_no_messages():
    db = _mock_db([])
    result = await fetch_sent_samples(db, CONN_ID, USER_ID)
    assert result == []


@pytest.mark.asyncio
async def test_fetch_sent_samples_respects_max_total():
    db_messages = [_make_db_message(f"msg-{i}", days_ago=i) for i in range(100)]
    db = _mock_db(db_messages)

    result = await fetch_sent_samples(db, CONN_ID, USER_ID, max_total=20)

    assert len(result) <= 20
