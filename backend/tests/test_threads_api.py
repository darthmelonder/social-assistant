"""Unit tests for the threads API routes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

THREAD_ID   = uuid.uuid4()
USER_ID     = uuid.uuid4()
ANALYSIS_ID = uuid.uuid4()


def _mock_user() -> MagicMock:
    u = MagicMock()
    u.id = USER_ID
    u.email = "user@example.com"
    return u


def _mock_thread(thread_id: uuid.UUID = THREAD_ID, user_id: uuid.UUID = USER_ID) -> MagicMock:
    t = MagicMock()
    t.id = thread_id
    t.user_id = user_id
    t.connection_id = uuid.uuid4()
    t.subject = "Q2 Report"
    t.snippet = "Please review..."
    t.last_message_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    t.is_unread = True
    t.participants = [{"email": "alice@example.com", "name": "Alice", "role": "recipient"}]
    t.deleted_at = None
    return t


def _mock_analysis() -> MagicMock:
    from app.models.enums import PriorityLevel, SentimentType
    a = MagicMock()
    a.id = ANALYSIS_ID
    a.thread_id = THREAD_ID
    a.priority = PriorityLevel.IMPORTANT
    a.priority_confidence = 0.85
    a.summary = "Alice requests review of Q2 report."
    a.action_items = [{"description": "Review report", "due_date_hint": None, "assignee_hint": None}]
    a.requires_reply = True
    a.sentiment = SentimentType.NEUTRAL
    return a


def _mock_message() -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.platform_message_id = "msg-1"
    m.from_email = "alice@example.com"
    m.from_name = "Alice"
    m.to_emails = ["me@example.com"]
    m.cc_emails = []
    m.subject = "Q2 Report"
    m.body_plain = "Please review."
    m.snippet = "Please review."
    m.internal_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    m.folder = "inbox"
    m.labels = ["INBOX", "UNREAD"]
    m.is_sent_by_user = False
    m.has_attachments = False
    m.deleted_at = None
    return m


def _mock_draft() -> MagicMock:
    d = MagicMock()
    d.id = uuid.uuid4()
    d.subject_line = "Re: Q2 Report"
    d.body_plain = "Hi Alice, I'll review it."
    d.body_html = "<p>Hi Alice, I'll review it.</p>"
    d.tone_used = "professional"
    d.status = MagicMock()
    d.status.value = "pending_review"
    d.regeneration_count = 0
    return d


def _setup_client(mock_db) -> TestClient:
    from app.api.deps import get_current_user, get_db
    from app.main import app

    async def _db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _mock_user()
    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ── GET /api/v1/threads ───────────────────────────────────────────────────────

def test_list_threads_returns_200():
    db = AsyncMock()
    # calls: threads, analyses, drafts
    threads_result = MagicMock()
    threads_result.scalars.return_value.all.return_value = [_mock_thread()]
    analyses_result = MagicMock()
    analyses_result.scalars.return_value.all.return_value = []
    drafts_result = MagicMock()
    drafts_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [threads_result, analyses_result, drafts_result]

    for c in _setup_client(db):
        resp = c.get("/api/v1/threads")
        assert resp.status_code == 200


def test_list_threads_returns_threads_and_cursor():
    db = AsyncMock()
    threads_result = MagicMock()
    threads_result.scalars.return_value.all.return_value = [_mock_thread()]
    analyses_result = MagicMock()
    analyses_result.scalars.return_value.all.return_value = []
    drafts_result = MagicMock()
    drafts_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [threads_result, analyses_result, drafts_result]

    for c in _setup_client(db):
        data = c.get("/api/v1/threads").json()
        assert "threads" in data
        assert "next_cursor" in data


def test_list_threads_empty_inbox():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result

    for c in _setup_client(db):
        data = c.get("/api/v1/threads").json()
        assert data["threads"] == []
        assert data["next_cursor"] is None


def test_list_threads_includes_analysis_data():
    db = AsyncMock()
    thread = _mock_thread()
    analysis = _mock_analysis()
    analysis.thread_id = thread.id

    threads_result = MagicMock()
    threads_result.scalars.return_value.all.return_value = [thread]
    analyses_result = MagicMock()
    analyses_result.scalars.return_value.all.return_value = [analysis]
    drafts_result = MagicMock()
    drafts_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [threads_result, analyses_result, drafts_result]

    for c in _setup_client(db):
        data = c.get("/api/v1/threads").json()
        thread_data = data["threads"][0]
        assert thread_data["priority"] == "important"
        assert thread_data["requires_reply"] is True


def test_list_threads_priority_none_when_not_triaged():
    db = AsyncMock()
    threads_result = MagicMock()
    threads_result.scalars.return_value.all.return_value = [_mock_thread()]
    no_data = MagicMock()
    no_data.scalars.return_value.all.return_value = []
    db.execute.side_effect = [threads_result, no_data, no_data]

    for c in _setup_client(db):
        data = c.get("/api/v1/threads").json()
        assert data["threads"][0]["priority"] is None


def test_list_threads_invalid_priority_returns_400():
    db = AsyncMock()
    # With priority filter, query goes to subquery path first
    subq_result = MagicMock()
    subq_result.first.return_value = None
    db.execute.return_value = subq_result

    for c in _setup_client(db):
        resp = c.get("/api/v1/threads?priority=banana")
        assert resp.status_code == 400


def test_list_threads_requires_auth():
    from app.main import app
    with TestClient(app) as c:
        resp = c.get("/api/v1/threads")
    assert resp.status_code == 401


# ── GET /api/v1/threads/:id ───────────────────────────────────────────────────

def test_get_thread_returns_200():
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = _mock_thread()
    msgs_result = MagicMock()
    msgs_result.scalars.return_value.all.return_value = [_mock_message()]
    analysis_result = MagicMock()
    analysis_result.scalar_one_or_none.return_value = _mock_analysis()
    draft_result = MagicMock()
    draft_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [thread_result, msgs_result, analysis_result, draft_result]

    for c in _setup_client(db):
        resp = c.get(f"/api/v1/threads/{THREAD_ID}")
        assert resp.status_code == 200


def test_get_thread_includes_messages():
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = _mock_thread()
    msgs_result = MagicMock()
    msgs_result.scalars.return_value.all.return_value = [_mock_message()]
    analysis_result = MagicMock()
    analysis_result.scalar_one_or_none.return_value = None
    draft_result = MagicMock()
    draft_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [thread_result, msgs_result, analysis_result, draft_result]

    for c in _setup_client(db):
        data = c.get(f"/api/v1/threads/{THREAD_ID}").json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["from_email"] == "alice@example.com"


def test_get_thread_returns_404_for_missing():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.get(f"/api/v1/threads/{uuid.uuid4()}")
        assert resp.status_code == 404


def test_get_thread_enforces_user_scoping():
    """Thread from another user should return 404 (scoped query returns None)."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # scoped query returned nothing
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.get(f"/api/v1/threads/{THREAD_ID}")
        assert resp.status_code == 404


def test_get_thread_analysis_none_when_not_triaged():
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = _mock_thread()
    msgs_result = MagicMock()
    msgs_result.scalars.return_value.all.return_value = []
    no_data = MagicMock()
    no_data.scalar_one_or_none.return_value = None
    db.execute.side_effect = [thread_result, msgs_result, no_data, no_data]

    for c in _setup_client(db):
        data = c.get(f"/api/v1/threads/{THREAD_ID}").json()
        assert data["analysis"] is None
        assert data["draft"] is None


# ── POST /api/v1/threads/:id/retriage ────────────────────────────────────────

def test_retriage_returns_202():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _mock_thread()
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.post(f"/api/v1/threads/{THREAD_ID}/retriage")
        assert resp.status_code == 202


def test_retriage_returns_job_id():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _mock_thread()
    db.execute.return_value = result

    for c in _setup_client(db):
        data = c.post(f"/api/v1/threads/{THREAD_ID}/retriage").json()
        assert "job_id" in data
        uuid.UUID(data["job_id"])


def test_retriage_returns_404_for_missing_thread():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.post(f"/api/v1/threads/{uuid.uuid4()}/retriage")
        assert resp.status_code == 404


# ── PATCH /api/v1/threads/:id ─────────────────────────────────────────────────

def test_patch_thread_priority_returns_200():
    db = AsyncMock()
    thread = _mock_thread()
    analysis = _mock_analysis()

    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = thread
    analysis_result = MagicMock()
    analysis_result.scalar_one_or_none.return_value = analysis
    db.execute.side_effect = [thread_result, analysis_result]

    for c in _setup_client(db):
        resp = c.patch(f"/api/v1/threads/{THREAD_ID}", json={"priority_override": "maybe"})
        assert resp.status_code == 200


def test_patch_thread_invalid_priority_returns_400():
    db = AsyncMock()
    thread = _mock_thread()
    analysis = _mock_analysis()

    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = thread
    analysis_result = MagicMock()
    analysis_result.scalar_one_or_none.return_value = analysis
    db.execute.side_effect = [thread_result, analysis_result]

    for c in _setup_client(db):
        resp = c.patch(f"/api/v1/threads/{THREAD_ID}", json={"priority_override": "banana"})
        assert resp.status_code == 400
