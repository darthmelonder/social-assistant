"""Unit tests for GoogleOAuthService — all HTTP calls are mocked."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.google_oauth import (
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    GoogleOAuthError,
    GoogleOAuthService,
    GoogleTokenBundle,
    GoogleUserInfo,
    get_google_oauth_service,
)

SVC = GoogleOAuthService(
    client_id="test-client-id",
    client_secret="test-secret",
    redirect_uri="http://localhost:8000/api/v1/auth/google/callback",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_http_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


def _mock_async_client(response: MagicMock) -> MagicMock:
    """Return a mock that satisfies `async with httpx.AsyncClient() as client:`."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = response
    mock_client.get.return_value = response
    return mock_client


# ── get_authorize_url ─────────────────────────────────────────────────────────

def test_authorize_url_starts_with_google_auth_url():
    url = SVC.get_authorize_url(state="random-state")
    assert url.startswith(GOOGLE_AUTH_URL)


def test_authorize_url_contains_client_id():
    url = SVC.get_authorize_url(state="s")
    assert "test-client-id" in url


def test_authorize_url_contains_state():
    url = SVC.get_authorize_url(state="my-state-token")
    assert "my-state-token" in url


def test_authorize_url_requests_offline_access():
    url = SVC.get_authorize_url(state="s")
    assert "offline" in url


def test_authorize_url_requests_gmail_readonly():
    url = SVC.get_authorize_url(state="s")
    assert "gmail.readonly" in url


# ── exchange_code ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exchange_code_success():
    mock_resp = _mock_http_response(200, {
        "access_token": "ya29.access",
        "refresh_token": "1//refresh",
        "expires_in": 3600,
        "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        "token_type": "Bearer",
    })
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=_mock_async_client(mock_resp)):
        result = await SVC.exchange_code("auth-code")

    assert result.access_token == "ya29.access"
    assert result.refresh_token == "1//refresh"
    assert result.expires_in == 3600
    assert isinstance(result, GoogleTokenBundle)


@pytest.mark.asyncio
async def test_exchange_code_without_refresh_token():
    mock_resp = _mock_http_response(200, {
        "access_token": "ya29.access",
        "expires_in": 3600,
        "scope": "openid",
        "token_type": "Bearer",
    })
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=_mock_async_client(mock_resp)):
        result = await SVC.exchange_code("auth-code")

    assert result.refresh_token is None


@pytest.mark.asyncio
async def test_exchange_code_google_error_raises():
    mock_resp = _mock_http_response(400, {"error": "invalid_grant"})
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=_mock_async_client(mock_resp)):
        with pytest.raises(GoogleOAuthError, match="400"):
            await SVC.exchange_code("bad-code")


# ── get_user_info ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_user_info_success():
    mock_resp = _mock_http_response(200, {
        "sub": "1234567890",
        "email": "user@gmail.com",
        "email_verified": True,
        "name": "Test User",
        "picture": "https://example.com/photo.jpg",
    })
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=_mock_async_client(mock_resp)):
        result = await SVC.get_user_info("ya29.access")

    assert result.sub == "1234567890"
    assert result.email == "user@gmail.com"
    assert result.email_verified is True
    assert result.name == "Test User"
    assert isinstance(result, GoogleUserInfo)


@pytest.mark.asyncio
async def test_get_user_info_missing_optional_fields():
    mock_resp = _mock_http_response(200, {
        "sub": "999",
        "email": "minimal@gmail.com",
        "email_verified": False,
    })
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=_mock_async_client(mock_resp)):
        result = await SVC.get_user_info("token")

    assert result.name is None
    assert result.picture is None


@pytest.mark.asyncio
async def test_get_user_info_error_raises():
    mock_resp = _mock_http_response(401, {"error": "invalid_token"})
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=_mock_async_client(mock_resp)):
        with pytest.raises(GoogleOAuthError, match="401"):
            await SVC.get_user_info("expired-token")


# ── refresh_access_token ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_access_token_success():
    mock_resp = _mock_http_response(200, {
        "access_token": "ya29.new-access",
        "expires_in": 3600,
        "scope": "openid",
        "token_type": "Bearer",
    })
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=_mock_async_client(mock_resp)):
        result = await SVC.refresh_access_token("1//old-refresh")

    assert result.access_token == "ya29.new-access"
    # When Google doesn't return a new refresh token, the old one is kept
    assert result.refresh_token == "1//old-refresh"


@pytest.mark.asyncio
async def test_refresh_access_token_error_raises():
    mock_resp = _mock_http_response(400, {"error": "invalid_grant"})
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=_mock_async_client(mock_resp)):
        with pytest.raises(GoogleOAuthError, match="400"):
            await SVC.refresh_access_token("revoked-refresh")


# ── revoke_token ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_revoke_token_does_not_raise_on_error():
    mock_resp = _mock_http_response(400, {"error": "invalid_token"})
    mock_client = _mock_async_client(mock_resp)
    with patch("app.services.google_oauth.httpx.AsyncClient", return_value=mock_client):
        # Revocation failures are non-fatal
        await SVC.revoke_token("some-token")


# ── factory ───────────────────────────────────────────────────────────────────

def test_factory_returns_service_instance():
    svc = get_google_oauth_service()
    assert isinstance(svc, GoogleOAuthService)
