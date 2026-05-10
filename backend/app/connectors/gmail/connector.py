"""GmailConnector — read-only Gmail adapter implementing PlatformConnector.

Strict read-only: only gmail.readonly scope is requested. No write operations.
Rate limiting is enforced per-connection via GmailRateLimiter.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import getaddresses, parseaddr

import httpx

from app.connectors.base import PlatformConnector
from app.connectors.gmail.mime_parser import (
    extract_html,
    extract_plain_text,
    get_header,
    has_attachments,
    parse_headers,
)
from app.connectors.gmail.rate_limiter import (
    COST_HISTORY_LIST,
    COST_MESSAGES_GET,
    COST_THREADS_GET,
    COST_THREADS_LIST,
    GmailRateLimiter,
)
from app.connectors.types import (
    CheckpointExpiredError,
    FetchChangesResult,
    FetchOptions,
    FetchPageResult,
    FolderType,
    LabelsChangedMutation,
    MessageAddedMutation,
    MessageDeletedMutation,
    Participant,
    PlatformMutation,
    RateLimitState,
    RawMessage,
    RawThread,
    ThreadDeletedMutation,
    TokenBundle,
)
from app.models.enums import PlatformType

# ── Gmail API endpoints ────────────────────────────────────────────────────────

_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# ── Label ↔ folder mapping ─────────────────────────────────────────────────────

_FOLDER_TO_LABEL: dict[str, str] = {
    "inbox": "INBOX",
    "sent": "SENT",
    "spam": "SPAM",
    "trash": "TRASH",
    "draft": "DRAFT",
}

_LABEL_TO_FOLDER: dict[str, FolderType] = {
    "INBOX": "inbox",
    "SENT": "sent",
    "SPAM": "spam",
    "TRASH": "trash",
    "DRAFT": "draft",
}


# ── Errors ─────────────────────────────────────────────────────────────────────

class GmailAPIError(Exception):
    pass

class GmailAuthError(GmailAPIError):
    """401 — access token expired or revoked."""

class GmailNotFoundError(GmailAPIError):
    """404 — resource not found or historyId expired."""

class GmailRateLimitError(GmailAPIError):
    """429 — quota exceeded."""


# ── Module-level helpers ───────────────────────────────────────────────────────

def _parse_email_address(value: str) -> tuple[str | None, str]:
    """Parse 'Name <email>' → (name_or_None, email)."""
    name, addr = parseaddr(value)
    return name.strip() or None, addr.strip() or value.strip()


def _parse_email_list(value: str) -> list[str]:
    """Parse a comma-separated address header into a flat email list."""
    return [addr for _, addr in getaddresses([value]) if addr]


def _parse_internal_date(ms_str: str | int) -> datetime:
    """Convert Gmail's internalDate (ms since epoch) to a timezone-aware datetime."""
    return datetime.fromtimestamp(int(ms_str) / 1000, tz=timezone.utc)


def _determine_folder(label_ids: list[str]) -> FolderType:
    """Map a message's Gmail labelIds to a normalised FolderType."""
    label_set = set(label_ids)
    for label, folder in _LABEL_TO_FOLDER.items():
        if label in label_set:
            return folder
    return "other"


# ── Connector ──────────────────────────────────────────────────────────────────

class GmailConnector(PlatformConnector):
    """Read-only Gmail connector.  Ingestion Worker calls this; auth routes use
    GoogleOAuthService instead.  Both hit the same Google APIs — they are
    separate app layers with different concerns.
    """

    def __init__(self) -> None:
        from app.core.config import get_settings
        s = get_settings()
        self._client_id = s.GOOGLE_CLIENT_ID
        self._client_secret = s.GOOGLE_CLIENT_SECRET
        self._rate_limiter = GmailRateLimiter()

    @property
    def platform(self) -> PlatformType:
        return PlatformType.GMAIL

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def exchange_auth_code(self, code: str, redirect_uri: str) -> TokenBundle:
        async with httpx.AsyncClient() as client:
            resp = await client.post(_TOKEN_URL, data={
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
        _raise_for_token_error(resp)
        data = resp.json()

        user_info = await self._fetch_user_info(data["access_token"])
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))

        return TokenBundle(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            granted_scopes=data.get("scope", "").split(),
            platform_account_id=user_info["sub"],
            platform_email=user_info.get("email"),
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenBundle:
        async with httpx.AsyncClient() as client:
            resp = await client.post(_TOKEN_URL, data={
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            })
        _raise_for_token_error(resp)
        data = resp.json()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))

        return TokenBundle(
            access_token=data["access_token"],
            # Google rarely rotates refresh tokens; keep the old one if absent
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=expires_at,
            granted_scopes=data.get("scope", "").split(),
            platform_account_id="",   # not returned on refresh; caller keeps existing
            platform_email=None,
        )

    async def revoke_tokens(self, token: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(_REVOKE_URL, params={"token": token})
        # Non-fatal — token will expire naturally if revocation fails

    # ── Full sync ─────────────────────────────────────────────────────────────

    async def fetch_page(
        self,
        access_token: str,
        cursor: str | None,
        options: FetchOptions,
    ) -> FetchPageResult:
        """Fetch one page of threads. Calls threads.list then threads.get per thread."""
        params: dict = {"maxResults": options.max_results}
        if options.folders:
            label = _FOLDER_TO_LABEL.get(options.folders[0])
            if label:
                params["labelIds"] = label
        if cursor:
            params["pageToken"] = cursor
        if options.date_from:
            params["q"] = f"after:{options.date_from.strftime('%Y/%m/%d')}"

        list_data = await self._get(access_token, f"{_GMAIL_BASE}/threads", params)

        messages: list[RawMessage] = []
        latest_history_id = "0"

        for stub in list_data.get("threads", []):
            thread_data = await self._get(
                access_token,
                f"{_GMAIL_BASE}/threads/{stub['id']}",
                {"format": "full"},
            )
            history_id = thread_data.get("historyId", "0")
            if int(history_id) > int(latest_history_id):
                latest_history_id = history_id

            for msg_data in thread_data.get("messages", []):
                messages.append(self._parse_message(msg_data))

        return FetchPageResult(
            messages=messages,
            next_cursor=list_data.get("nextPageToken"),
            sync_checkpoint=latest_history_id,
        )

    # ── Incremental sync ──────────────────────────────────────────────────────

    async def fetch_changes(
        self,
        access_token: str,
        checkpoint: str,
    ) -> FetchChangesResult:
        """Fetch mutations since checkpoint. Raises CheckpointExpiredError on 404."""
        try:
            data = await self._get(
                access_token,
                f"{_GMAIL_BASE}/history",
                {
                    "startHistoryId": checkpoint,
                    "historyTypes": "messageAdded,messageDeleted,labelAdded,labelRemoved",
                },
            )
        except GmailNotFoundError:
            raise CheckpointExpiredError(
                f"Gmail historyId {checkpoint!r} has expired; full re-sync required"
            )

        mutations: list[PlatformMutation] = []
        for record in data.get("history", []):
            for item in record.get("messagesAdded", []):
                msg = item["message"]
                mutations.append(MessageAddedMutation(
                    platform_message_id=msg["id"],
                    platform_thread_id=msg["threadId"],
                ))
            for item in record.get("messagesDeleted", []):
                mutations.append(MessageDeletedMutation(
                    platform_message_id=item["message"]["id"],
                ))
            for item in record.get("labelsAdded", []):
                mutations.append(LabelsChangedMutation(
                    platform_message_id=item["message"]["id"],
                    labels_added=tuple(item.get("labelIds", [])),
                    labels_removed=(),
                ))
            for item in record.get("labelsRemoved", []):
                mutations.append(LabelsChangedMutation(
                    platform_message_id=item["message"]["id"],
                    labels_added=(),
                    labels_removed=tuple(item.get("labelIds", [])),
                ))

        return FetchChangesResult(
            mutations=mutations,
            new_checkpoint=data.get("historyId", checkpoint),
        )

    # ── Individual fetches ────────────────────────────────────────────────────

    async def fetch_message(self, access_token: str, platform_message_id: str) -> RawMessage:
        data = await self._get(
            access_token,
            f"{_GMAIL_BASE}/messages/{platform_message_id}",
            {"format": "full"},
        )
        return self._parse_message(data)

    async def fetch_thread(self, access_token: str, platform_thread_id: str) -> RawThread:
        data = await self._get(
            access_token,
            f"{_GMAIL_BASE}/threads/{platform_thread_id}",
            {"format": "full"},
        )
        return self._parse_thread(data)

    # ── Rate limit ────────────────────────────────────────────────────────────

    def get_rate_limit_state(self, connection_id: str) -> RateLimitState:
        state = self._rate_limiter.get_state(connection_id)
        return RateLimitState(
            quota_remaining=state["quota_remaining"],
            quota_per_second=state["quota_per_second"],
            retry_after_ms=None,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get(self, access_token: str, url: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params or {},
            )
        if resp.status_code == 401:
            raise GmailAuthError("Access token invalid or expired")
        if resp.status_code == 404:
            raise GmailNotFoundError(resp.text)
        if resp.status_code == 429:
            raise GmailRateLimitError("Gmail API quota exceeded")
        resp.raise_for_status()
        return resp.json()

    async def _fetch_user_info(self, access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        resp.raise_for_status()
        return resp.json()

    def _parse_message(self, msg_data: dict) -> RawMessage:
        label_ids: list[str] = msg_data.get("labelIds", [])
        payload: dict = msg_data.get("payload", {})
        headers = parse_headers(payload.get("headers", []))

        from_val = get_header(headers, "From") or ""
        from_name, from_email = _parse_email_address(from_val)

        return RawMessage(
            platform_message_id=msg_data["id"],
            platform_thread_id=msg_data["threadId"],
            from_email=from_email,
            from_name=from_name,
            to_emails=_parse_email_list(get_header(headers, "To") or ""),
            cc_emails=_parse_email_list(get_header(headers, "Cc") or ""),
            subject=get_header(headers, "Subject"),
            body_plain=extract_plain_text(payload),
            body_html=extract_html(payload),
            snippet=msg_data.get("snippet"),
            internal_date=_parse_internal_date(msg_data.get("internalDate", "0")),
            labels=label_ids,
            folder=_determine_folder(label_ids),
            has_attachments=has_attachments(payload),
            attachment_metadata=[],
            is_sent_by_user="SENT" in label_ids,
            raw_headers=headers,
        )

    def _parse_thread(self, thread_data: dict) -> RawThread:
        messages = [self._parse_message(m) for m in thread_data.get("messages", [])]

        seen: dict[str, Participant] = {}
        for msg in messages:
            if msg.from_email not in seen:
                role = "sender" if msg.is_sent_by_user else "recipient"
                seen[msg.from_email] = Participant(
                    email=msg.from_email, name=msg.from_name, role=role
                )

        subject = messages[0].subject if messages else None

        return RawThread(
            platform_thread_id=thread_data["id"],
            subject=subject,
            messages=messages,
            participants=list(seen.values()),
        )


# ── Private helpers ────────────────────────────────────────────────────────────

def _raise_for_token_error(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise GmailAuthError(f"Token request rejected: {resp.text}")
    if not resp.is_success:
        raise GmailAPIError(f"Token request failed ({resp.status_code}): {resp.text}")
