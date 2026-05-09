import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt


class InvalidTokenError(Exception):
    """Raised when a JWT is missing, expired, tampered, or wrong type."""


@dataclass(frozen=True)
class TokenPayload:
    user_id: uuid.UUID
    token_type: str    # "access" | "refresh"
    expires_at: datetime


def create_access_token(user_id: uuid.UUID) -> str:
    from app.core.config import get_settings
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": expire},
        s.JWT_SECRET,
        algorithm=s.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    from app.core.config import get_settings
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=s.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "type": "refresh", "exp": expire},
        s.JWT_SECRET,
        algorithm=s.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> TokenPayload:
    return _decode(token, expected_type="access")


def decode_refresh_token(token: str) -> TokenPayload:
    return _decode(token, expected_type="refresh")


def _decode(token: str, expected_type: str) -> TokenPayload:
    from app.core.config import get_settings
    s = get_settings()
    try:
        payload = jwt.decode(token, s.JWT_SECRET, algorithms=[s.JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(
            f"Expected token type '{expected_type}', got '{payload.get('type')}'"
        )

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("Token missing valid subject") from exc

    return TokenPayload(
        user_id=user_id,
        token_type=payload["type"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )
