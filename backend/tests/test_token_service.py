"""Unit tests for token decryption and refresh service."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.encryption import TokenEncryptionService
from app.services.token_service import (
    REFRESH_BUFFER_MINUTES,
    TokenRefreshError,
    decrypt_access_token,
    get_valid_access_token,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

TEST_KEY = bytes.fromhex("ab" * 32)
ENC_SVC = TokenEncryptionService(key=TEST_KEY, key_id="v1")

ACCESS_TOKEN = "ya29.valid-access-token"
REFRESH_TOKEN = "1//valid-refresh-token"


def _make_connection(
    expires_in_minutes: int = 60,
    access_token: str = ACCESS_TOKEN,
    refresh_token: str | None = REFRESH_TOKEN,
) -> MagicMock:
    """Build a mock PlatformConnection with encrypted tokens."""
    enc_access = ENC_SVC.encrypt(access_token)
    conn = MagicMock()
    conn.id = uuid.uuid4()
    conn.encrypted_access_token = enc_access.ciphertext
    conn.token_iv = enc_access.iv
    conn.token_tag = enc_access.tag
    conn.token_key_id = "v1"
    conn.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

    if refresh_token is not None:
        enc_refresh = ENC_SVC.encrypt(refresh_token)
        conn.encrypted_refresh_token = enc_refresh.to_blob()
    else:
        conn.encrypted_refresh_token = None

    return conn


def _make_connector(new_access_token: str = "ya29.refreshed") -> AsyncMock:
    from app.connectors.types import TokenBundle
    connector = AsyncMock()
    connector.refresh_access_token.return_value = TokenBundle(
        access_token=new_access_token,
        refresh_token=None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        granted_scopes=["gmail.readonly"],
        platform_account_id="",
        platform_email=None,
    )
    return connector


# ── decrypt_access_token ──────────────────────────────────────────────────────

def test_decrypt_access_token_returns_plaintext():
    conn = _make_connection()
    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        result = decrypt_access_token(conn)
    assert result == ACCESS_TOKEN


def test_decrypt_access_token_different_plaintext():
    conn = _make_connection(access_token="ya29.another-token")
    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        result = decrypt_access_token(conn)
    assert result == "ya29.another-token"


# ── get_valid_access_token — token still valid ────────────────────────────────

@pytest.mark.asyncio
async def test_returns_existing_token_when_not_expired():
    conn = _make_connection(expires_in_minutes=60)
    connector = _make_connector()
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        result = await get_valid_access_token(conn, connector, db)

    assert result == ACCESS_TOKEN
    connector.refresh_access_token.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_does_not_refresh_when_within_buffer():
    # Token expires in REFRESH_BUFFER_MINUTES + 1 — should NOT refresh
    conn = _make_connection(expires_in_minutes=REFRESH_BUFFER_MINUTES + 1)
    connector = _make_connector()
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        result = await get_valid_access_token(conn, connector, db)

    assert result == ACCESS_TOKEN
    connector.refresh_access_token.assert_not_called()


# ── get_valid_access_token — token expired / expiring ────────────────────────

@pytest.mark.asyncio
async def test_refreshes_when_token_expired():
    conn = _make_connection(expires_in_minutes=-5)  # already expired
    connector = _make_connector(new_access_token="ya29.brand-new")
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        result = await get_valid_access_token(conn, connector, db)

    assert result == "ya29.brand-new"
    connector.refresh_access_token.assert_called_once_with(REFRESH_TOKEN)
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_refreshes_when_expiring_within_buffer():
    # Token expires in REFRESH_BUFFER_MINUTES - 1 — should trigger refresh
    conn = _make_connection(expires_in_minutes=REFRESH_BUFFER_MINUTES - 1)
    connector = _make_connector()
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        await get_valid_access_token(conn, connector, db)

    connector.refresh_access_token.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_updates_connection_tokens():
    conn = _make_connection(expires_in_minutes=-1)
    connector = _make_connector(new_access_token="ya29.new")
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        await get_valid_access_token(conn, connector, db)

    # New encrypted access token persisted on connection
    assert conn.encrypted_access_token is not None
    assert conn.token_iv is not None
    assert conn.token_tag is not None
    assert conn.token_expires_at is not None


@pytest.mark.asyncio
async def test_refresh_updates_expires_at():
    conn = _make_connection(expires_in_minutes=-1)
    old_expires = conn.token_expires_at
    connector = _make_connector()
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        await get_valid_access_token(conn, connector, db)

    assert conn.token_expires_at > old_expires


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token_when_google_provides_new_one():
    conn = _make_connection(expires_in_minutes=-1)
    original_blob = conn.encrypted_refresh_token

    from app.connectors.types import TokenBundle
    connector = AsyncMock()
    connector.refresh_access_token.return_value = TokenBundle(
        access_token="ya29.new",
        refresh_token="1//brand-new-refresh",  # Google rotated it
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        granted_scopes=[],
        platform_account_id="",
        platform_email=None,
    )
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        await get_valid_access_token(conn, connector, db)

    # Refresh token blob should have changed
    assert conn.encrypted_refresh_token != original_blob


@pytest.mark.asyncio
async def test_refresh_keeps_old_refresh_token_when_google_omits():
    conn = _make_connection(expires_in_minutes=-1)
    original_blob = conn.encrypted_refresh_token

    connector = _make_connector()  # refresh_token=None in bundle (Google didn't rotate)
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        await get_valid_access_token(conn, connector, db)

    # Blob unchanged — Google didn't issue a new one
    assert conn.encrypted_refresh_token == original_blob


# ── Error cases ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_raises_when_expired_and_no_refresh_token():
    conn = _make_connection(expires_in_minutes=-1, refresh_token=None)
    connector = _make_connector()
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        with pytest.raises(TokenRefreshError, match="no refresh token"):
            await get_valid_access_token(conn, connector, db)


@pytest.mark.asyncio
async def test_raises_when_connector_refresh_fails():
    conn = _make_connection(expires_in_minutes=-1)
    connector = AsyncMock()
    connector.refresh_access_token.side_effect = Exception("Google API error")
    db = AsyncMock()

    with patch("app.services.token_service.get_encryption_service", return_value=ENC_SVC):
        with pytest.raises(TokenRefreshError, match="refresh failed"):
            await get_valid_access_token(conn, connector, db)
