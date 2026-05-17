"""Unit tests for the connections API routes."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.models.enums import ConnectionStatus

CONN_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _mock_user(user_id: uuid.UUID = USER_ID) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.email = "user@example.com"
    return u


def _mock_conn(
    conn_id: uuid.UUID = CONN_ID,
    user_id: uuid.UUID = USER_ID,
    status: ConnectionStatus = ConnectionStatus.ACTIVE,
) -> MagicMock:
    c = MagicMock()
    c.id = conn_id
    c.user_id = user_id
    c.platform = "gmail"
    c.platform_email = "user@gmail.com"
    c.status = status
    c.last_synced_at = None
    c.last_sync_error = None
    c.granted_scopes = ["gmail.readonly"]
    c.created_at = None
    return c


def _setup_client(mock_user, mock_db) -> TestClient:
    from app.api.deps import get_current_user, get_db, get_redis
    from app.main import app

    async def _db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_redis] = lambda: AsyncMock()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    mock_user = _mock_user()
    mock_db = AsyncMock()

    result = MagicMock()
    result.scalars.return_value.all.return_value = [_mock_conn()]
    result.scalar_one_or_none.return_value = _mock_conn()
    mock_db.execute.return_value = result

    yield from _setup_client(mock_user, mock_db)


# ── GET /api/v1/connections ───────────────────────────────────────────────────

def test_list_connections_returns_200(client):
    resp = client.get("/api/v1/connections")
    assert resp.status_code == 200


def test_list_connections_returns_list(client):
    resp = client.get("/api/v1/connections")
    assert isinstance(resp.json(), list)


def test_list_connections_includes_platform_field(client):
    resp = client.get("/api/v1/connections")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["platform"] == "gmail"


def test_list_connections_requires_auth():
    from app.main import app
    with TestClient(app) as c:
        resp = c.get("/api/v1/connections")
    assert resp.status_code == 401


# ── GET /api/v1/connections/:id ───────────────────────────────────────────────

def test_get_connection_returns_200(client):
    resp = client.get(f"/api/v1/connections/{CONN_ID}")
    assert resp.status_code == 200


def test_get_connection_returns_404_when_not_found():
    mock_user = _mock_user()
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    for c in _setup_client(mock_user, mock_db):
        resp = c.get(f"/api/v1/connections/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── DELETE /api/v1/connections/:id ────────────────────────────────────────────

def test_disconnect_returns_204(client):
    resp = client.delete(f"/api/v1/connections/{CONN_ID}")
    assert resp.status_code == 204


def test_disconnect_marks_status_revoked():
    mock_user = _mock_user()
    mock_db = AsyncMock()
    conn = _mock_conn()
    result = MagicMock()
    result.scalar_one_or_none.return_value = conn
    mock_db.execute.return_value = result

    for c in _setup_client(mock_user, mock_db):
        c.delete(f"/api/v1/connections/{CONN_ID}")

    assert conn.status == ConnectionStatus.REVOKED


def test_disconnect_returns_404_for_other_user():
    mock_user = _mock_user(user_id=uuid.uuid4())  # different user
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # scoped query returns nothing
    mock_db.execute.return_value = result

    for c in _setup_client(mock_user, mock_db):
        resp = c.delete(f"/api/v1/connections/{CONN_ID}")
        assert resp.status_code == 404


# ── POST /api/v1/connections/:id/sync ────────────────────────────────────────

def test_trigger_sync_returns_202(client):
    resp = client.post(f"/api/v1/connections/{CONN_ID}/sync")
    assert resp.status_code == 202


def test_trigger_sync_returns_job_id(client):
    resp = client.post(f"/api/v1/connections/{CONN_ID}/sync")
    data = resp.json()
    assert "job_id" in data
    # job_id should be a valid UUID string
    uuid.UUID(data["job_id"])


def test_trigger_sync_returns_404_for_missing_connection():
    mock_user = _mock_user()
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    for c in _setup_client(mock_user, mock_db):
        resp = c.post(f"/api/v1/connections/{uuid.uuid4()}/sync")
        assert resp.status_code == 404
