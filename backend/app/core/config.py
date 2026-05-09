from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Encryption — 64 hex chars = 32-byte AES-256 key
    TOKEN_ENCRYPTION_KEY: str

    # Google OAuth2
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    # Anthropic
    ANTHROPIC_API_KEY: str

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS — set as JSON array in env: CORS_ORIGINS=["http://localhost:3000"]
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("TOKEN_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if len(v) != 64:
            raise ValueError("TOKEN_ENCRYPTION_KEY must be 64 hex characters (32 bytes)")
        try:
            bytes.fromhex(v)
        except ValueError as exc:
            raise ValueError("TOKEN_ENCRYPTION_KEY must be valid hex") from exc
        return v

    @property
    def encryption_key_bytes(self) -> bytes:
        return bytes.fromhex(self.TOKEN_ENCRYPTION_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()
