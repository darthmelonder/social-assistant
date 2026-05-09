import os

# Set required env vars before any app module is imported.
# os.environ.setdefault preserves real env vars already set (e.g. in CI).
_TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_social_assistant",
    "REDIS_URL": "redis://localhost:6379/1",
    "TOKEN_ENCRYPTION_KEY": "ab" * 32,  # 64 hex chars = 32 bytes
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
    "GOOGLE_REDIRECT_URI": "http://localhost:8000/api/v1/auth/google/callback",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "JWT_SECRET": "test-jwt-secret-for-unit-tests-only",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def valid_env(monkeypatch) -> dict:
    """Provides a complete, valid set of env vars for Settings instantiation."""
    env = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "TOKEN_ENCRYPTION_KEY": "cd" * 32,
        "GOOGLE_CLIENT_ID": "gid",
        "GOOGLE_CLIENT_SECRET": "gsecret",
        "GOOGLE_REDIRECT_URI": "http://localhost/cb",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "JWT_SECRET": "jwtsecret",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env
