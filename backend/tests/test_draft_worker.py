"""Unit tests for the draft worker.

Tests call run_draft_generate directly — no ARQ, Claude, or real DB needed.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import DraftStatus
from app.workers.draft.service import DraftResult
from app.workers.draft.worker import run_draft_generate

THREAD_ID   = uuid.uuid4()
USER_ID     = uuid.uuid4()
ANALYSIS_ID = uuid.uuid4()
_W          = "app.workers.draft.worker"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _thread() -> MagicMock:
    t = MagicMock()
    t.id = THREAD_ID
    t.user_id = USER_ID
    t.subject = "Project Update"
    return t


def _msg(msg_id: str = "msg-1") -> MagicMock:
    m = MagicMock()
    m.platform_message_id = msg_id
    m.from_email = "alice@example.com"
    m.body_plain = "Please send the update."
    m.is_sent_by_user = False
    return m


_DEFAULT_ITEMS = [{"description": "Send weekly update", "due_date_hint": None, "assignee_hint": None}]

def _analysis(action_items: list | None = _DEFAULT_ITEMS) -> MagicMock:
    a = MagicMock()
    a.id = ANALYSIS_ID
    a.action_items = action_items  # None is a valid value — worker converts it to []
    return a


def _draft_result(**kwargs) -> DraftResult:
    defaults = dict(
        body_plain="Hi Alice,\n\nHere is the update you requested.\n\nBest,\nJatin",
        subject_line="Re: Project Update",
        body_html="<p>Hi Alice,</p><p>Here is the update.</p>",
        tone_used="professional and warm",
        model_id="claude-sonnet-4-6",
        model_version="claude-sonnet-4-6",
        prompt_template_hash="abc123hash",
        input_tokens=600,
        output_tokens=180,
        cache_read_tokens=500,
        cache_write_tokens=100,
    )
    defaults.update(kwargs)
    return DraftResult(**defaults)


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_draft_generate_returns_draft():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result()):
        result = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    from app.models.draft import Draft
    assert isinstance(result, Draft)


@pytest.mark.asyncio
async def test_run_draft_generate_sets_body_plain():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result(body_plain="Here is my reply.")):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.body_plain == "Here is my reply."


@pytest.mark.asyncio
async def test_run_draft_generate_sets_subject_line():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result(subject_line="Re: Update")):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.subject_line == "Re: Update"


@pytest.mark.asyncio
async def test_run_draft_generate_sets_body_html():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result(body_html="<p>Reply</p>")):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.body_html == "<p>Reply</p>"


@pytest.mark.asyncio
async def test_run_draft_generate_sets_tone_used():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result(tone_used="concise and direct")):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.tone_used == "concise and direct"


@pytest.mark.asyncio
async def test_run_draft_generate_status_is_pending_review():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result()):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.status == DraftStatus.PENDING_REVIEW


@pytest.mark.asyncio
async def test_run_draft_generate_sets_ids():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result()):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.thread_id == THREAD_ID
    assert draft.user_id == USER_ID
    assert draft.analysis_id == ANALYSIS_ID


@pytest.mark.asyncio
async def test_run_draft_generate_sets_model_provenance():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result(
        model_id="claude-opus-4-7",
        input_tokens=1200,
        cache_read_tokens=1000,
        cache_write_tokens=200,
    )):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.model_id == "claude-opus-4-7"
    assert draft.input_tokens == 1200
    assert draft.cache_read_tokens == 1000
    assert draft.cache_write_tokens == 200


@pytest.mark.asyncio
async def test_run_draft_generate_sets_prompt_hash():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result(prompt_template_hash="deadbeef")):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.prompt_template_hash == "deadbeef"


@pytest.mark.asyncio
async def test_run_draft_generate_adds_to_session():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result()):
        await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_draft_generate_commits():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result()):
        await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    db.commit.assert_called_once()


# ── Action items forwarding ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_draft_generate_passes_action_items_to_service():
    db = _mock_db()
    items = [{"description": "Send the report", "due_date_hint": "Friday", "assignee_hint": None}]
    analysis = _analysis(action_items=items)

    with patch(f"{_W}.generate_draft", return_value=_draft_result()) as mock_gen:
        await run_draft_generate(db, _thread(), [_msg()], analysis, None, [])

    call_kwargs = mock_gen.call_args
    assert call_kwargs[0][2] == items  # third positional arg is action_items


@pytest.mark.asyncio
async def test_run_draft_generate_handles_none_action_items():
    db = _mock_db()
    analysis = _analysis(action_items=None)
    with patch(f"{_W}.generate_draft", return_value=_draft_result()) as mock_gen:
        await run_draft_generate(db, _thread(), [_msg()], analysis, None, [])
    # Should pass empty list, not None
    call_kwargs = mock_gen.call_args
    assert call_kwargs[0][2] == []


# ── Subject line None ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_draft_generate_handles_none_subject_line():
    db = _mock_db()
    with patch(f"{_W}.generate_draft", return_value=_draft_result(subject_line=None)):
        draft = await run_draft_generate(db, _thread(), [_msg()], _analysis(), None, [])
    assert draft.subject_line is None


# ── WorkerSettings registration ───────────────────────────────────────────────

def test_draft_generate_job_registered_in_worker_settings():
    from app.workers.arq_settings import WorkerSettings
    from app.workers.draft.worker import draft_generate_job
    fn_names = [f.__name__ for f in WorkerSettings.functions]
    assert "draft_generate_job" in fn_names
