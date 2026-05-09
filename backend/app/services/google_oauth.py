from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

GMAIL_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
])


class GoogleOAuthError(Exception):
    pass


@dataclass(frozen=True)
class GoogleTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str


@dataclass(frozen=True)
class GoogleUserInfo:
    sub: str             # stable Google account ID
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


class GoogleOAuthService:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def get_authorize_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": GMAIL_SCOPES,
            "access_type": "offline",
            "prompt": "consent",  # always request refresh token
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> GoogleTokenBundle:
        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
            })
        if resp.status_code != 200:
            raise GoogleOAuthError(f"Token exchange failed ({resp.status_code}): {resp.text}")
        data = resp.json()
        return GoogleTokenBundle(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in", 3600),
            scope=data.get("scope", ""),
        )

    async def get_user_info(self, access_token: str) -> GoogleUserInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code != 200:
            raise GoogleOAuthError(f"User info fetch failed ({resp.status_code}): {resp.text}")
        data = resp.json()
        return GoogleUserInfo(
            sub=data["sub"],
            email=data["email"],
            email_verified=data.get("email_verified", False),
            name=data.get("name"),
            picture=data.get("picture"),
        )

    async def refresh_access_token(self, refresh_token: str) -> GoogleTokenBundle:
        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            })
        if resp.status_code != 200:
            raise GoogleOAuthError(f"Token refresh failed ({resp.status_code}): {resp.text}")
        data = resp.json()
        return GoogleTokenBundle(
            access_token=data["access_token"],
            # Google only returns a new refresh_token occasionally; keep the old one
            refresh_token=data.get("refresh_token", refresh_token),
            expires_in=data.get("expires_in", 3600),
            scope=data.get("scope", ""),
        )

    async def revoke_token(self, token: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(GOOGLE_REVOKE_URL, params={"token": token})
        # Revocation failures are non-fatal — token will expire naturally


def get_google_oauth_service() -> GoogleOAuthService:
    from app.core.config import get_settings
    s = get_settings()
    return GoogleOAuthService(
        client_id=s.GOOGLE_CLIENT_ID,
        client_secret=s.GOOGLE_CLIENT_SECRET,
        redirect_uri=s.GOOGLE_REDIRECT_URI,
    )
