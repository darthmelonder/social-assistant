"""Unit tests for the profile rebuild worker.

Tests call run_profile_rebuild directly with mocked deps — no ARQ, Claude,
or real DB needed.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.profile.builder import ProfileResult
from app.workers.profile.sampler import SentMessageSample
from app.workers.profile.worker import run_profile_rebuild

# ── Fixtures ──────────────────────────────────────────────────────────────────

CONN_ID = uuid.uuid4()
USER_ID = uuid.uuid4()

_W = "app.workers.profile.worker"


def _conn() -> MagicMock:
    c = MagicMock()
    c.id = CONN_ID
    c.user_id = USER_ID
    return c


def _sample(days_ago: int = 30, msg_id: str = "msg-1") -> SentMessageSample:
    return SentMessageSample(
        platform_message_id=msg_id,
        subject="Test",
        body_plain="Hello world this is a test email.",
        internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        to_emails=["to@example.com"],
        word_count=7,
    )


def _profile_result(**kwargs) -> ProfileResult:
    defaults = dict(
        voice_summary="The user writes concisely.",
        tone_attributes=["professional", "concise"],
        attributes={
            "formality_score": 0.7,
            "vocabulary_sample": ["regarding", "please find"],
            "topic_clusters": [],
            "greeting_patterns": ["Hi"],
            "sign_off_patterns": ["Best"],
            "avg_email_length_words": 80,
        },
        model_id="claude-sonnet-4-6",
        model_version="claude-sonnet-4-6",
        prompt_template_hash="abc123",
        input_tokens=1000,
        output_tokens=300,
        cache_read_tokens=800,
        cache_write_tokens=200,
        messages_analyzed_count=5,
    )
    defaults.update(kwargs)
    return ProfileResult(**defaults)


def _mock_db(existing_profile=None) -> AsyncMock:
    """Build a mock AsyncSession for the profile worker.

    execute() is called twice: once to SELECT the existing profile,
    once to UPDATE it to is_current=False.
    """
    db = AsyncMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = existing_profile
    db.execute.side_effect = [select_result, MagicMock()]
    db.add = MagicMock()
    return db


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_profile_rebuild_returns_user_profile():
    db = _mock_db()
    samples = [_sample()]

    with patch(f"{_W}.fetch_sent_samples", return_value=samples), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        result = await run_profile_rebuild(db, _conn())

    from app.models.user_profile import UserProfile
    assert isinstance(result, UserProfile)


@pytest.mark.asyncio
async def test_run_profile_rebuild_calls_build_profile_with_samples():
    db = _mock_db()
    samples = [_sample("msg-1"), _sample("msg-2")]

    with patch(f"{_W}.fetch_sent_samples", return_value=samples), \
         patch(f"{_W}.build_profile", return_value=_profile_result()) as mock_build:
        await run_profile_rebuild(db, _conn())

    mock_build.assert_called_once_with(samples)


@pytest.mark.asyncio
async def test_run_profile_rebuild_sets_voice_summary():
    db = _mock_db()
    result_data = _profile_result(voice_summary="Writes very clearly.")

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=result_data):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.voice_summary == "Writes very clearly."


@pytest.mark.asyncio
async def test_run_profile_rebuild_sets_tone_attributes():
    db = _mock_db()
    result_data = _profile_result(tone_attributes=["warm", "direct"])

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=result_data):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.tone_attributes == ["warm", "direct"]


@pytest.mark.asyncio
async def test_run_profile_rebuild_sets_attributes_jsonb():
    db = _mock_db()
    attrs = {"formality_score": 0.8, "vocabulary_sample": ["kindly", "please"]}
    result_data = _profile_result(attributes=attrs)

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=result_data):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.attributes["formality_score"] == 0.8


@pytest.mark.asyncio
async def test_run_profile_rebuild_sets_model_provenance():
    db = _mock_db()
    result_data = _profile_result(
        model_id="claude-opus-4-7",
        input_tokens=5000,
        cache_read_tokens=4000,
        cache_write_tokens=1000,
    )

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=result_data):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.model_id == "claude-opus-4-7"
    assert profile.input_tokens == 5000
    assert profile.cache_read_tokens == 4000
    assert profile.cache_write_tokens == 1000


@pytest.mark.asyncio
async def test_run_profile_rebuild_sets_messages_analyzed_count():
    db = _mock_db()
    samples = [_sample(msg_id=f"m{i}") for i in range(8)]

    with patch(f"{_W}.fetch_sent_samples", return_value=samples), \
         patch(f"{_W}.build_profile", return_value=_profile_result(messages_analyzed_count=8)):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.messages_analyzed_count == 8


@pytest.mark.asyncio
async def test_run_profile_rebuild_sets_analyzed_date_range():
    db = _mock_db()
    samples = [
        SentMessageSample("m1", "Subj", "Body", datetime(2026, 1, 1, tzinfo=timezone.utc), [], 1),
        SentMessageSample("m2", "Subj", "Body", datetime(2026, 6, 15, tzinfo=timezone.utc), [], 1),
    ]

    with patch(f"{_W}.fetch_sent_samples", return_value=samples), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.analyzed_date_range_start == date(2026, 1, 1)
    assert profile.analyzed_date_range_end == date(2026, 6, 15)


@pytest.mark.asyncio
async def test_run_profile_rebuild_sets_connection_and_user_ids():
    db = _mock_db()

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.connection_id == CONN_ID
    assert profile.user_id == USER_ID


@pytest.mark.asyncio
async def test_run_profile_rebuild_new_profile_is_current():
    db = _mock_db()

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.is_current is True


@pytest.mark.asyncio
async def test_run_profile_rebuild_commits():
    db = _mock_db()

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        await run_profile_rebuild(db, _conn())

    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_run_profile_rebuild_adds_profile_to_session():
    db = _mock_db()

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        await run_profile_rebuild(db, _conn())

    db.add.assert_called_once()


# ── Profile versioning ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_first_profile_gets_version_1():
    db = _mock_db(existing_profile=None)

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.profile_version == 1


@pytest.mark.asyncio
async def test_subsequent_profile_increments_version():
    existing = MagicMock()
    existing.profile_version = 3
    db = _mock_db(existing_profile=existing)

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        profile = await run_profile_rebuild(db, _conn())

    assert profile.profile_version == 4


@pytest.mark.asyncio
async def test_old_profile_marked_not_current():
    """The UPDATE to is_current=False must be executed."""
    db = _mock_db(existing_profile=None)

    with patch(f"{_W}.fetch_sent_samples", return_value=[_sample()]), \
         patch(f"{_W}.build_profile", return_value=_profile_result()):
        await run_profile_rebuild(db, _conn())

    # Two execute calls: SELECT existing + UPDATE is_current=False
    assert db.execute.call_count == 2


# ── No samples — graceful no-op ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_none_when_no_sent_messages():
    db = AsyncMock()

    with patch(f"{_W}.fetch_sent_samples", return_value=[]), \
         patch(f"{_W}.build_profile") as mock_build:
        result = await run_profile_rebuild(db, _conn())

    assert result is None
    mock_build.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_skips_db_writes_when_no_samples():
    db = AsyncMock()

    with patch(f"{_W}.fetch_sent_samples", return_value=[]):
        await run_profile_rebuild(db, _conn())

    db.add.assert_not_called()


# ── WorkerSettings registration ───────────────────────────────────────────────

def test_profile_rebuild_job_registered_in_worker_settings():
    from app.workers.arq_settings import WorkerSettings
    from app.workers.profile.worker import profile_rebuild_job

    fn_names = [f.__name__ for f in WorkerSettings.functions]
    assert "profile_rebuild_job" in fn_names
