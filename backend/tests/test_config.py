import pytest
from pydantic import ValidationError

# All tests instantiate Settings() directly (not get_settings()) so that
# monkeypatch env-var changes take effect without lru_cache interference.
# _env_file=None disables .env file loading so tests are hermetic.


def test_loads_required_fields(valid_env):
    from app.core.config import Settings

    s = Settings(_env_file=None)

    assert s.DATABASE_URL == valid_env["DATABASE_URL"]
    assert s.REDIS_URL == valid_env["REDIS_URL"]
    assert s.GOOGLE_CLIENT_ID == valid_env["GOOGLE_CLIENT_ID"]
    assert s.ANTHROPIC_API_KEY == valid_env["ANTHROPIC_API_KEY"]
    assert s.JWT_SECRET == valid_env["JWT_SECRET"]


def test_default_values(valid_env):
    from app.core.config import Settings

    s = Settings(_env_file=None)

    assert s.JWT_ALGORITHM == "HS256"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert s.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert s.CORS_ORIGINS == ["http://localhost:3000"]


def test_encryption_key_bytes_conversion(valid_env):
    from app.core.config import Settings

    s = Settings(_env_file=None)

    expected = bytes.fromhex(valid_env["TOKEN_ENCRYPTION_KEY"])
    assert s.encryption_key_bytes == expected
    assert len(s.encryption_key_bytes) == 32


def test_invalid_encryption_key_wrong_length(valid_env, monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "tooshort")

    with pytest.raises(ValidationError) as exc_info:
        from app.core.config import Settings
        Settings(_env_file=None)

    assert "64 hex characters" in str(exc_info.value)


def test_invalid_encryption_key_not_hex(valid_env, monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "zz" * 32)  # right length, not hex

    with pytest.raises(ValidationError) as exc_info:
        from app.core.config import Settings
        Settings(_env_file=None)

    assert "valid hex" in str(exc_info.value)


def test_cors_origins_parsed_from_json_array(valid_env, monkeypatch):
    # pydantic-settings parses list[str] fields from JSON arrays in env vars
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000","http://localhost:3001"]')

    from app.core.config import Settings

    s = Settings(_env_file=None)

    assert s.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:3001"]


def test_cors_origins_default_when_not_set(valid_env):
    from app.core.config import Settings

    s = Settings(_env_file=None)

    assert s.CORS_ORIGINS == ["http://localhost:3000"]


def test_missing_required_field_raises(valid_env, monkeypatch):
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError):
        from app.core.config import Settings
        Settings(_env_file=None)


def test_get_settings_is_cached():
    from app.core.config import get_settings

    s1 = get_settings()
    s2 = get_settings()

    assert s1 is s2
