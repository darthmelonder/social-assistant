"""Unit tests for auth API routes.

DB and Google OAuth calls are fully mocked — no real network or DB needed.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services.google_oauth import GoogleOAuthError, GoogleTokenBundle, GoogleUserInfo
from app.services.jwt_service import create_access_token, create_refresh_token

# ── Fixtures ──────────────────────────────────────────────────────────────────

FAKE_USER_ID = uuid.uuid4()
FAKE_USER_EMAIL = "user@gmail.com"

FAKE_TOKEN_BUNDLE = GoogleTokenBundle(
    access_token="ya29.google-access",
    refresh_token="1//google-refresh",
    expires_in=3600,
    scope="openid email profile https://www.googleapis.com/auth/gmail.readonly",
)
FAKE_USER_INFO = GoogleUserInfo(
    sub="google-sub-123",
    email=FAKE_USER_EMAIL,
    email_verified=True,
    name="Test User",
    picture="https://example.com/pic.jpg",
)


def _make_db_session(user=None, conn=None) -> AsyncMock:
    """Build a mock AsyncSession for dependency injection."""
    session = AsyncMock()

    # Two sequential execute() calls: first for User lookup, second for PlatformConnection
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user
    conn_result = MagicMock()
    conn_result.scalar_one_or_none.return_value = conn
    session.execute.side_effect = [user_result, conn_result]

    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def client_with_mock_db(monkeypatch) -> TestClient:
    """TestClient with get_db overridden to a mock session (new user scenario)."""
    from app.core.database import get_db
    from app.main import app

    mock_session = _make_db_session(user=None, conn=None)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── GET /api/v1/auth/google/authorize ─────────────────────────────────────────

def test_authorize_returns_url(client):
    resp = client.get("/api/v1/auth/google/authorize")
    assert resp.status_code == 200
    data = resp.json()
    assert "authorize_url" in data
    assert "accounts.google.com" in data["authorize_url"]


def test_authorize_returns_state(client):
    resp = client.get("/api/v1/auth/google/authorize")
    data = resp.json()
    assert "state" in data
    assert len(data["state"]) > 8


def test_authorize_state_differs_between_calls(client):
    r1 = client.get("/api/v1/auth/google/authorize").json()
    r2 = client.get("/api/v1/auth/google/authorize").json()
    assert r1["state"] != r2["state"]


# ── GET /api/v1/auth/google/callback — new user ───────────────────────────────

def test_callback_new_user_returns_access_token(client_with_mock_db):
    with patch("app.api.routes.auth.get_google_oauth_service") as mock_svc_factory:
        mock_svc = AsyncMock()
        mock_svc.exchange_code.return_value = FAKE_TOKEN_BUNDLE
        mock_svc.get_user_info.return_value = FAKE_USER_INFO
        mock_svc_factory.return_value = mock_svc

        resp = client_with_mock_db.get("/api/v1/auth/google/callback?code=auth-code&state=s")

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_callback_new_user_returns_user_info(client_with_mock_db):
    with patch("app.api.routes.auth.get_google_oauth_service") as mock_svc_factory:
        mock_svc = AsyncMock()
        mock_svc.exchange_code.return_value = FAKE_TOKEN_BUNDLE
        mock_svc.get_user_info.return_value = FAKE_USER_INFO
        mock_svc_factory.return_value = mock_svc

        resp = client_with_mock_db.get("/api/v1/auth/google/callback?code=auth-code&state=s")

    user = resp.json()["user"]
    assert user["email"] == FAKE_USER_EMAIL
    assert user["display_name"] == "Test User"


def test_callback_sets_refresh_cookie(client_with_mock_db):
    with patch("app.api.routes.auth.get_google_oauth_service") as mock_svc_factory:
        mock_svc = AsyncMock()
        mock_svc.exchange_code.return_value = FAKE_TOKEN_BUNDLE
        mock_svc.get_user_info.return_value = FAKE_USER_INFO
        mock_svc_factory.return_value = mock_svc

        resp = client_with_mock_db.get("/api/v1/auth/google/callback?code=auth-code&state=s")

    assert "refresh_token" in resp.cookies


def test_callback_google_error_returns_400(client_with_mock_db):
    with patch("app.api.routes.auth.get_google_oauth_service") as mock_svc_factory:
        mock_svc = AsyncMock()
        mock_svc.exchange_code.side_effect = GoogleOAuthError("invalid_grant")
        mock_svc_factory.return_value = mock_svc

        resp = client_with_mock_db.get("/api/v1/auth/google/callback?code=bad&state=s")

    assert resp.status_code == 400
    assert "invalid_grant" in resp.json()["detail"]


def test_callback_missing_code_returns_422(client):
    resp = client.get("/api/v1/auth/google/callback?state=s")
    assert resp.status_code == 422


# ── Callback — existing user ──────────────────────────────────────────────────

def test_callback_existing_user_updates_connection():
    from app.core.database import get_db
    from app.main import app
    from app.models.user import User
    from app.models.platform_connection import PlatformConnection

    existing_user = MagicMock(spec=User)
    existing_user.id = FAKE_USER_ID
    existing_user.email = FAKE_USER_EMAIL
    existing_user.display_name = "Old Name"
    existing_user.is_active = True

    existing_conn = MagicMock(spec=PlatformConnection)

    mock_session = _make_db_session(user=existing_user, conn=existing_conn)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        with patch("app.api.routes.auth.get_google_oauth_service") as mock_svc_factory:
            mock_svc = AsyncMock()
            mock_svc.exchange_code.return_value = FAKE_TOKEN_BUNDLE
            mock_svc.get_user_info.return_value = FAKE_USER_INFO
            mock_svc_factory.return_value = mock_svc

            resp = c.get("/api/v1/auth/google/callback?code=code&state=s")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    # display_name updated on existing user
    assert existing_user.display_name == "Test User"
    # Connection fields updated
    assert existing_conn.status is not None


# ── POST /api/v1/auth/refresh ─────────────────────────────────────────────────

def test_refresh_with_valid_cookie_returns_new_access_token(client):
    refresh_tok = create_refresh_token(FAKE_USER_ID)
    client.cookies.set("refresh_token", refresh_tok)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_refresh_without_cookie_returns_401(client):
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


def test_refresh_with_invalid_token_returns_401(client):
    client.cookies.set("refresh_token", "garbage.token.here")
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


def test_refresh_with_access_token_in_cookie_returns_401(client):
    # Access tokens must not be accepted as refresh tokens
    wrong_tok = create_access_token(FAKE_USER_ID)
    client.cookies.set("refresh_token", wrong_tok)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


# ── POST /api/v1/auth/logout ──────────────────────────────────────────────────

def test_logout_returns_204(client):
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204


def test_logout_clears_refresh_cookie(client):
    client.cookies.set("refresh_token", "some-token")
    resp = client.post("/api/v1/auth/logout")
    # Cookie cleared — should be absent or empty
    assert resp.cookies.get("refresh_token", "") == ""


# ── GET /api/v1/auth/me ───────────────────────────────────────────────────────

def test_me_with_valid_token_returns_user(client):
    from app.core.database import get_db
    from app.main import app
    from app.models.user import User

    mock_user = MagicMock(spec=User)
    mock_user.id = FAKE_USER_ID
    mock_user.email = FAKE_USER_EMAIL
    mock_user.display_name = "Test User"
    mock_user.avatar_url = None
    mock_user.is_active = True

    mock_session = AsyncMock()
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = user_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    access_tok = create_access_token(FAKE_USER_ID)
    with TestClient(app) as c:
        resp = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_tok}"})

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == FAKE_USER_EMAIL
    assert data["id"] == str(FAKE_USER_ID)


def test_me_without_token_returns_401(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token_returns_401(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
