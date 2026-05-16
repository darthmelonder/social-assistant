"""Unit tests for the triage worker.

Tests call run_triage directly — no ARQ, Claude, or real DB needed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import PriorityLevel, SentimentType
from app.workers.triage.service import TriageResult
from app.workers.triage.worker import run_triage

# ── Constants ─────────────────────────────────────────────────────────────────

THREAD_ID = uuid.uuid4()
USER_ID   = uuid.uuid4()
_W        = "app.workers.triage.worker"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _thread() -> MagicMock:
    t = MagicMock()
    t.id = THREAD_ID
    t.user_id = USER_ID
    t.subject = "Q2 Report"
    return t


def _msg(msg_id: str = "msg-1") -> MagicMock:
    m = MagicMock()
    m.platform_message_id = msg_id
    m.from_email = "alice@example.com"
    m.body_plain = "Please review."
    m.is_sent_by_user = False
    m.internal_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    return m


def _triage_result(**kwargs) -> TriageResult:
    defaults = dict(
        priority="important",
        priority_confidence=0.85,
        summary="Alice requests feedback on Q2 report.",
        action_items=[{"description": "Review report", "due_date_hint": None, "assignee_hint": None}],
        requires_reply=True,
        sentiment="neutral",
        source_message_ids=["msg-1"],
        source_message_hash="abc123hash",
        model_id="claude-sonnet-4-6",
        model_version="claude-sonnet-4-6",
        prompt_template_hash="def456",
        input_tokens=500,
        output_tokens=150,
        cache_read_tokens=400,
        cache_write_tokens=100,
    )
    defaults.update(kwargs)
    return TriageResult(**defaults)


def _mock_db(existing_analysis=None) -> AsyncMock:
    """Mock DB with select → existing analysis, then update call."""
    db = AsyncMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = existing_analysis
    db.execute.side_effect = [select_result, MagicMock()]  # [SELECT, UPDATE]
    db.add = MagicMock()
    return db


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_triage_returns_thread_analysis():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result()):
        result = await run_triage(db, _thread(), [_msg()], profile=None)
    from app.models.thread_analysis import ThreadAnalysis
    assert isinstance(result, ThreadAnalysis)


@pytest.mark.asyncio
async def test_run_triage_sets_priority():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(priority="urgent")):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.priority == PriorityLevel.URGENT


@pytest.mark.asyncio
async def test_run_triage_sets_summary():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(summary="Needs immediate action.")):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.summary == "Needs immediate action."


@pytest.mark.asyncio
async def test_run_triage_sets_action_items():
    items = [{"description": "Reply by Friday", "due_date_hint": "Friday", "assignee_hint": None}]
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(action_items=items)):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.action_items == items


@pytest.mark.asyncio
async def test_run_triage_sets_requires_reply():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(requires_reply=True)):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.requires_reply is True


@pytest.mark.asyncio
async def test_run_triage_sets_sentiment():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(sentiment="positive")):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.sentiment == SentimentType.POSITIVE


@pytest.mark.asyncio
async def test_run_triage_sets_none_sentiment_when_absent():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(sentiment=None)):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.sentiment is None


@pytest.mark.asyncio
async def test_run_triage_sets_source_message_hash():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(source_message_hash="deadbeef")):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.source_message_hash == "deadbeef"


@pytest.mark.asyncio
async def test_run_triage_sets_model_provenance():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(
        model_id="claude-opus-4-7", input_tokens=1000, cache_read_tokens=800
    )):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.model_id == "claude-opus-4-7"
    assert analysis.input_tokens == 1000
    assert analysis.cache_read_tokens == 800


@pytest.mark.asyncio
async def test_run_triage_sets_is_current_true():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result()):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.is_current is True


@pytest.mark.asyncio
async def test_run_triage_sets_thread_and_user_ids():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result()):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.thread_id == THREAD_ID
    assert analysis.user_id == USER_ID


@pytest.mark.asyncio
async def test_run_triage_adds_to_session():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result()):
        await run_triage(db, _thread(), [_msg()], profile=None)
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_triage_commits():
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result()):
        await run_triage(db, _thread(), [_msg()], profile=None)
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_run_triage_supersedes_old_analysis():
    """Two execute calls: SELECT existing + UPDATE is_current=False."""
    db = _mock_db(existing_analysis=None)
    with patch(f"{_W}.triage_thread", return_value=_triage_result()):
        await run_triage(db, _thread(), [_msg()], profile=None)
    assert db.execute.call_count == 2


# ── No-op when content unchanged ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_triage_skips_when_hash_unchanged():
    """If the source_message_hash matches the existing analysis, skip re-write."""
    existing = MagicMock()
    existing.source_message_hash = "same_hash"

    db = AsyncMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = existing
    db.execute.return_value = select_result
    db.add = MagicMock()

    with patch(f"{_W}.triage_thread", return_value=_triage_result(source_message_hash="same_hash")):
        result = await run_triage(db, _thread(), [_msg()], profile=None)

    assert result is None
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_run_triage_proceeds_when_hash_changed():
    """Different hash → new analysis written even when an old one exists."""
    existing = MagicMock()
    existing.source_message_hash = "old_hash"

    db = _mock_db(existing_analysis=existing)
    with patch(f"{_W}.triage_thread", return_value=_triage_result(source_message_hash="new_hash")):
        result = await run_triage(db, _thread(), [_msg()], profile=None)

    assert result is not None
    db.add.assert_called_once()


# ── No-op when no messages ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_triage_returns_none_for_empty_messages():
    db = AsyncMock()
    with patch(f"{_W}.triage_thread") as mock_triage:
        result = await run_triage(db, _thread(), [], profile=None)
    assert result is None
    mock_triage.assert_not_called()
    db.commit.assert_not_called()


# ── Priority enum conversion ──────────────────────────────────────────────────

@pytest.mark.parametrize("priority_str,expected_enum", [
    ("urgent",    PriorityLevel.URGENT),
    ("important", PriorityLevel.IMPORTANT),
    ("maybe",     PriorityLevel.MAYBE),
    ("skip",      PriorityLevel.SKIP),
])
@pytest.mark.asyncio
async def test_run_triage_converts_all_priority_values(priority_str, expected_enum):
    db = _mock_db()
    with patch(f"{_W}.triage_thread", return_value=_triage_result(priority=priority_str)):
        analysis = await run_triage(db, _thread(), [_msg()], profile=None)
    assert analysis.priority == expected_enum


# ── WorkerSettings registration ───────────────────────────────────────────────

def test_triage_job_registered_in_worker_settings():
    from app.workers.arq_settings import WorkerSettings
    from app.workers.triage.worker import triage_job

    fn_names = [f.__name__ for f in WorkerSettings.functions]
    assert "triage_job" in fn_names


# ── Draft auto-trigger ────────────────────────────────────────────────────────

def _make_sf() -> MagicMock:
    """session_factory mock whose __call__ returns a proper async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=cm)


def _mock_thread() -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.user_id = uuid.uuid4()
    t.subject = "Test"
    return t


def _make_analysis(priority: PriorityLevel, requires_reply: bool) -> MagicMock:
    a = MagicMock()
    a.priority = priority
    a.requires_reply = requires_reply
    a.id = uuid.uuid4()
    return a


@pytest.mark.asyncio
async def test_triage_job_enqueues_draft_for_urgent_requires_reply():
    from app.workers.triage.worker import triage_job

    analysis = _make_analysis(PriorityLevel.URGENT, requires_reply=True)
    redis = AsyncMock()
    thread_id = str(uuid.uuid4())

    with patch("app.workers.triage.worker._load_triage_context",
               return_value=(_mock_thread(), [_mock_thread()], None)), \
         patch("app.workers.triage.worker.run_triage", return_value=analysis):
        await triage_job(
            {"session_factory": _make_sf(), "redis": redis},
            thread_id=thread_id,
        )

    redis.enqueue_job.assert_called_once_with(
        "draft_generate_job",
        thread_id=thread_id,
        analysis_id=str(analysis.id),
    )


@pytest.mark.asyncio
async def test_triage_job_enqueues_draft_for_important_requires_reply():
    from app.workers.triage.worker import triage_job

    analysis = _make_analysis(PriorityLevel.IMPORTANT, requires_reply=True)
    redis = AsyncMock()

    with patch("app.workers.triage.worker._load_triage_context",
               return_value=(_mock_thread(), [_mock_thread()], None)), \
         patch("app.workers.triage.worker.run_triage", return_value=analysis):
        await triage_job(
            {"session_factory": _make_sf(), "redis": redis},
            thread_id=str(uuid.uuid4()),
        )

    redis.enqueue_job.assert_called_once()


@pytest.mark.asyncio
async def test_triage_job_does_not_enqueue_draft_for_maybe():
    from app.workers.triage.worker import triage_job

    analysis = _make_analysis(PriorityLevel.MAYBE, requires_reply=True)
    redis = AsyncMock()

    with patch("app.workers.triage.worker._load_triage_context",
               return_value=(_mock_thread(), [_mock_thread()], None)), \
         patch("app.workers.triage.worker.run_triage", return_value=analysis):
        await triage_job(
            {"session_factory": _make_sf(), "redis": redis},
            thread_id=str(uuid.uuid4()),
        )

    redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_triage_job_does_not_enqueue_draft_when_no_reply_needed():
    from app.workers.triage.worker import triage_job

    analysis = _make_analysis(PriorityLevel.URGENT, requires_reply=False)
    redis = AsyncMock()

    with patch("app.workers.triage.worker._load_triage_context",
               return_value=(_mock_thread(), [_mock_thread()], None)), \
         patch("app.workers.triage.worker.run_triage", return_value=analysis):
        await triage_job(
            {"session_factory": _make_sf(), "redis": redis},
            thread_id=str(uuid.uuid4()),
        )

    redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_triage_job_no_draft_without_redis():
    from app.workers.triage.worker import triage_job

    analysis = _make_analysis(PriorityLevel.URGENT, requires_reply=True)

    with patch("app.workers.triage.worker._load_triage_context",
               return_value=(_mock_thread(), [_mock_thread()], None)), \
         patch("app.workers.triage.worker.run_triage", return_value=analysis):
        # ctx has no 'redis' — should not raise
        await triage_job({"session_factory": _make_sf()}, thread_id=str(uuid.uuid4()))
