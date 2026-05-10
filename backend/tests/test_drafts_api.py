"""Unit tests for drafts API routes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

THREAD_ID   = uuid.uuid4()
DRAFT_ID    = uuid.uuid4()
ANALYSIS_ID = uuid.uuid4()
USER_ID     = uuid.uuid4()


def _mock_user() -> MagicMock:
    u = MagicMock()
    u.id = USER_ID
    u.email = "user@example.com"
    return u


def _mock_thread() -> MagicMock:
    t = MagicMock()
    t.id = THREAD_ID
    t.user_id = USER_ID
    t.connection_id = uuid.uuid4()
    t.deleted_at = None
    return t


def _mock_draft(draft_id: uuid.UUID = DRAFT_ID) -> MagicMock:
    d = MagicMock()
    d.id = draft_id
    d.thread_id = THREAD_ID
    d.user_id = USER_ID
    d.subject_line = "Re: Q2 Report"
    d.body_plain = "Hi, here's the update."
    d.body_html = "<p>Hi, here's the update.</p>"
    d.tone_used = "professional"
    d.status = "pending_review"
    d.regeneration_count = 0
    d.generated_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    d.reviewed_at = None
    return d


def _mock_analysis() -> MagicMock:
    a = MagicMock()
    a.id = ANALYSIS_ID
    return a


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


# ── GET /api/v1/threads/:id/drafts ───────────────────────────────────────────

def test_list_drafts_returns_200():
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = _mock_thread()
    drafts_result = MagicMock()
    drafts_result.scalars.return_value.all.return_value = [_mock_draft()]
    db.execute.side_effect = [thread_result, drafts_result]

    for c in _setup_client(db):
        resp = c.get(f"/api/v1/threads/{THREAD_ID}/drafts")
        assert resp.status_code == 200


def test_list_drafts_returns_list():
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = _mock_thread()
    drafts_result = MagicMock()
    drafts_result.scalars.return_value.all.return_value = [_mock_draft()]
    db.execute.side_effect = [thread_result, drafts_result]

    for c in _setup_client(db):
        data = c.get(f"/api/v1/threads/{THREAD_ID}/drafts").json()
        assert isinstance(data, list)
        assert len(data) == 1


def test_list_drafts_returns_404_for_missing_thread():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.get(f"/api/v1/threads/{uuid.uuid4()}/drafts")
        assert resp.status_code == 404


# ── POST /api/v1/threads/:id/drafts ──────────────────────────────────────────

def test_request_draft_returns_202():
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = _mock_thread()
    analysis_result = MagicMock()
    analysis_result.scalar_one_or_none.return_value = _mock_analysis()
    db.execute.side_effect = [thread_result, analysis_result]

    for c in _setup_client(db):
        resp = c.post(f"/api/v1/threads/{THREAD_ID}/drafts")
        assert resp.status_code == 202


def test_request_draft_returns_job_id():
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = _mock_thread()
    analysis_result = MagicMock()
    analysis_result.scalar_one_or_none.return_value = _mock_analysis()
    db.execute.side_effect = [thread_result, analysis_result]

    for c in _setup_client(db):
        data = c.post(f"/api/v1/threads/{THREAD_ID}/drafts").json()
        assert "job_id" in data
        uuid.UUID(data["job_id"])


def test_request_draft_returns_400_when_no_analysis():
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = _mock_thread()
    analysis_result = MagicMock()
    analysis_result.scalar_one_or_none.return_value = None  # not triaged yet
    db.execute.side_effect = [thread_result, analysis_result]

    for c in _setup_client(db):
        resp = c.post(f"/api/v1/threads/{THREAD_ID}/drafts")
        assert resp.status_code == 400


# ── PATCH /api/v1/drafts/:id ─────────────────────────────────────────────────

def test_patch_draft_approve_returns_200():
    db = AsyncMock()
    draft = _mock_draft()
    result = MagicMock()
    result.scalar_one_or_none.return_value = draft
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.patch(f"/api/v1/drafts/{DRAFT_ID}", json={"status": "approved"})
        assert resp.status_code == 200


def test_patch_draft_sets_status():
    from app.models.enums import DraftStatus
    db = AsyncMock()
    draft = _mock_draft()
    result = MagicMock()
    result.scalar_one_or_none.return_value = draft
    db.execute.return_value = result

    for c in _setup_client(db):
        c.patch(f"/api/v1/drafts/{DRAFT_ID}", json={"status": "rejected"})

    assert draft.status == DraftStatus.REJECTED


def test_patch_draft_with_edited_body():
    db = AsyncMock()
    draft = _mock_draft()
    result = MagicMock()
    result.scalar_one_or_none.return_value = draft
    db.execute.return_value = result

    for c in _setup_client(db):
        c.patch(
            f"/api/v1/drafts/{DRAFT_ID}",
            json={"status": "copied", "user_edited_body": "My edited reply."},
        )

    assert draft.user_edited_body == "My edited reply."


def test_patch_draft_with_feedback_note():
    db = AsyncMock()
    draft = _mock_draft()
    result = MagicMock()
    result.scalar_one_or_none.return_value = draft
    db.execute.return_value = result

    for c in _setup_client(db):
        c.patch(
            f"/api/v1/drafts/{DRAFT_ID}",
            json={"status": "rejected", "feedback_note": "Too formal"},
        )

    assert draft.feedback_note == "Too formal"


def test_patch_draft_sets_reviewed_at():
    db = AsyncMock()
    draft = _mock_draft()
    draft.reviewed_at = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = draft
    db.execute.return_value = result

    for c in _setup_client(db):
        c.patch(f"/api/v1/drafts/{DRAFT_ID}", json={"status": "approved"})

    assert draft.reviewed_at is not None


def test_patch_draft_invalid_status_returns_422():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _mock_draft()
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.patch(f"/api/v1/drafts/{DRAFT_ID}", json={"status": "superseded"})
        assert resp.status_code == 422  # Pydantic Literal validation


def test_patch_draft_returns_404_for_missing():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.patch(f"/api/v1/drafts/{uuid.uuid4()}", json={"status": "approved"})
        assert resp.status_code == 404


def test_patch_draft_enforces_user_scoping():
    """Draft from another user should 404 (scoped query returns None)."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    for c in _setup_client(db):
        resp = c.patch(f"/api/v1/drafts/{DRAFT_ID}", json={"status": "approved"})
        assert resp.status_code == 404
