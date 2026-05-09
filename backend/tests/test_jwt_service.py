"""Unit tests for JWT issue and validation service."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.services.jwt_service import (
    InvalidTokenError,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)

USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


# ── Access token ──────────────────────────────────────────────────────────────

def test_access_token_roundtrip():
    token = create_access_token(USER_ID)
    payload = decode_access_token(token)
    assert payload.user_id == USER_ID
    assert payload.token_type == "access"


def test_access_token_returns_string():
    assert isinstance(create_access_token(USER_ID), str)


def test_access_token_has_future_expiry():
    token = create_access_token(USER_ID)
    payload = decode_access_token(token)
    assert payload.expires_at > datetime.now(timezone.utc)


def test_access_token_expiry_within_configured_window():
    from app.core.config import get_settings
    s = get_settings()
    token = create_access_token(USER_ID)
    payload = decode_access_token(token)
    expected_window = timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES)
    remaining = payload.expires_at - datetime.now(timezone.utc)
    assert remaining <= expected_window


# ── Refresh token ─────────────────────────────────────────────────────────────

def test_refresh_token_roundtrip():
    token = create_refresh_token(USER_ID)
    payload = decode_refresh_token(token)
    assert payload.user_id == USER_ID
    assert payload.token_type == "refresh"


def test_refresh_token_has_longer_expiry_than_access():
    access = create_access_token(USER_ID)
    refresh = create_refresh_token(USER_ID)
    access_exp = decode_access_token(access).expires_at
    refresh_exp = decode_refresh_token(refresh).expires_at
    assert refresh_exp > access_exp


# ── Cross-type rejection ──────────────────────────────────────────────────────

def test_access_token_rejected_by_refresh_decoder():
    token = create_access_token(USER_ID)
    with pytest.raises(InvalidTokenError, match="refresh"):
        decode_refresh_token(token)


def test_refresh_token_rejected_by_access_decoder():
    token = create_refresh_token(USER_ID)
    with pytest.raises(InvalidTokenError, match="access"):
        decode_access_token(token)


# ── Invalid / tampered tokens ─────────────────────────────────────────────────

def test_garbage_string_raises():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not.a.jwt.at.all")


def test_tampered_signature_raises():
    token = create_access_token(USER_ID)
    parts = token.split(".")
    parts[-1] = parts[-1][:-4] + "XXXX"
    with pytest.raises(InvalidTokenError):
        decode_access_token(".".join(parts))


def test_expired_token_raises():
    from app.core.config import get_settings
    s = get_settings()
    expired_payload = {
        "sub": str(USER_ID),
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    expired_token = jwt.encode(expired_payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError):
        decode_access_token(expired_token)


def test_token_signed_with_wrong_secret_raises():
    from app.core.config import get_settings
    s = get_settings()
    payload = {
        "sub": str(USER_ID),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    bad_token = jwt.encode(payload, "wrong-secret", algorithm=s.JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError):
        decode_access_token(bad_token)


def test_token_missing_sub_raises():
    from app.core.config import get_settings
    s = get_settings()
    payload = {
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        # no "sub" field
    }
    token = jwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError, match="subject"):
        decode_access_token(token)


def test_token_with_invalid_uuid_sub_raises():
    from app.core.config import get_settings
    s = get_settings()
    payload = {
        "sub": "not-a-uuid",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError, match="subject"):
        decode_access_token(token)


# ── UUID preservation ─────────────────────────────────────────────────────────

def test_uuid_v4_preserved_through_roundtrip():
    random_id = uuid.uuid4()
    token = create_access_token(random_id)
    payload = decode_access_token(token)
    assert payload.user_id == random_id


def test_payload_is_frozen_dataclass():
    token = create_access_token(USER_ID)
    payload = decode_access_token(token)
    assert isinstance(payload, TokenPayload)
    with pytest.raises(Exception):
        payload.user_id = uuid.uuid4()  # type: ignore[misc]
