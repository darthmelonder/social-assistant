"""Unit tests for GmailConnector — all HTTP mocked, no real network."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.gmail.connector import (
    GmailAuthError,
    GmailConnector,
    GmailNotFoundError,
    GmailRateLimitError,
    _determine_folder,
    _parse_email_address,
    _parse_email_list,
    _parse_internal_date,
)
from app.connectors.types import (
    CheckpointExpiredError,
    FetchOptions,
    LabelsChangedMutation,
    MessageAddedMutation,
    MessageDeletedMutation,
    RateLimitState,
)
from app.models.enums import PlatformType


# ── Fixtures / builders ───────────────────────────────────────────────────────

def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).rstrip(b"=").decode()


def _make_message(
    msg_id: str = "msg-1",
    thread_id: str = "thr-1",
    label_ids: list[str] | None = None,
    subject: str = "Test subject",
    from_addr: str = "sender@example.com",
    body: str = "Hello, world!",
    internal_date: str = "1704067200000",
    snippet: str = "Hello...",
) -> dict:
    if label_ids is None:
        label_ids = ["INBOX", "UNREAD"]
    return {
        "id": msg_id,
        "threadId": thread_id,
        "labelIds": label_ids,
        "snippet": snippet,
        "historyId": "9999",
        "internalDate": internal_date,
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": from_addr},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": subject},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "headers": [{"name": "Content-Type", "value": "text/plain; charset=utf-8"}],
                    "body": {"data": _b64(body), "size": len(body)},
                }
            ],
        },
    }


def _make_thread(thread_id: str = "thr-1", messages: list[dict] | None = None) -> dict:
    if messages is None:
        messages = [_make_message(thread_id=thread_id)]
    return {"id": thread_id, "historyId": "9999", "messages": messages}


def _make_threads_list(thread_ids: list[str], next_page: str | None = None) -> dict:
    result: dict = {"threads": [{"id": tid, "snippet": "..."} for tid in thread_ids]}
    if next_page:
        result["nextPageToken"] = next_page
    return result


def _make_history(
    added: list[tuple[str, str]] | None = None,
    deleted: list[str] | None = None,
    labels_added: list[tuple[str, list[str]]] | None = None,
    labels_removed: list[tuple[str, list[str]]] | None = None,
    new_history_id: str = "2000",
) -> dict:
    record: dict = {}
    if added:
        record["messagesAdded"] = [
            {"message": {"id": mid, "threadId": tid}} for mid, tid in added
        ]
    if deleted:
        record["messagesDeleted"] = [{"message": {"id": mid}} for mid in deleted]
    if labels_added:
        record["labelsAdded"] = [
            {"message": {"id": mid}, "labelIds": lbls} for mid, lbls in labels_added
        ]
    if labels_removed:
        record["labelsRemoved"] = [
            {"message": {"id": mid}, "labelIds": lbls} for mid, lbls in labels_removed
        ]
    return {"history": [record] if record else [], "historyId": new_history_id}


def _mock_response(status: int, data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data
    resp.text = str(data)
    resp.is_success = status < 400
    resp.raise_for_status = MagicMock()
    return resp


def _mock_client(*get_responses, post_response=None) -> MagicMock:
    """Build a mock AsyncClient with sequential GET responses."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.get.side_effect = list(get_responses)
    if post_response:
        client.post.return_value = post_response
    return client


@pytest.fixture
def connector() -> GmailConnector:
    return GmailConnector()


# ── platform property ─────────────────────────────────────────────────────────

def test_platform_is_gmail(connector):
    assert connector.platform == PlatformType.GMAIL


# ── Module-level helpers ──────────────────────────────────────────────────────

class TestParseEmailAddress:
    def test_full_name_and_address(self):
        name, addr = _parse_email_address("John Doe <john@example.com>")
        assert name == "John Doe"
        assert addr == "john@example.com"

    def test_bare_address(self):
        name, addr = _parse_email_address("john@example.com")
        assert name is None
        assert addr == "john@example.com"

    def test_empty_name(self):
        name, addr = _parse_email_address("<john@example.com>")
        assert name is None
        assert addr == "john@example.com"


class TestParseEmailList:
    def test_single_address(self):
        assert _parse_email_list("a@b.com") == ["a@b.com"]

    def test_multiple_addresses(self):
        result = _parse_email_list("a@b.com, C D <c@d.com>")
        assert "a@b.com" in result
        assert "c@d.com" in result

    def test_empty_string(self):
        assert _parse_email_list("") == []


class TestParseInternalDate:
    def test_converts_ms_to_datetime(self):
        dt = _parse_internal_date("1704067200000")
        assert dt == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_result_is_utc(self):
        dt = _parse_internal_date("0")
        assert dt.tzinfo == timezone.utc


class TestDetermineFolder:
    def test_inbox(self):
        assert _determine_folder(["INBOX", "UNREAD"]) == "inbox"

    def test_sent(self):
        assert _determine_folder(["SENT"]) == "sent"

    def test_spam(self):
        assert _determine_folder(["SPAM"]) == "spam"

    def test_trash(self):
        assert _determine_folder(["TRASH"]) == "trash"

    def test_draft(self):
        assert _determine_folder(["DRAFT"]) == "draft"

    def test_other_for_unknown_labels(self):
        assert _determine_folder(["CATEGORY_UPDATES"]) == "other"

    def test_inbox_takes_priority(self):
        # INBOX is listed first in _LABEL_TO_FOLDER — takes precedence
        assert _determine_folder(["INBOX", "SENT"]) == "inbox"


# ── exchange_auth_code ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exchange_auth_code_success(connector):
    token_resp = _mock_response(200, {
        "access_token": "ya29.access",
        "refresh_token": "1//refresh",
        "expires_in": 3600,
        "scope": "openid email https://www.googleapis.com/auth/gmail.readonly",
    })
    userinfo_resp = _mock_response(200, {
        "sub": "google-sub-123",
        "email": "user@gmail.com",
    })
    mock_client = _mock_client(userinfo_resp, post_response=token_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        bundle = await connector.exchange_auth_code("auth-code", "http://localhost/cb")

    assert bundle.access_token == "ya29.access"
    assert bundle.refresh_token == "1//refresh"
    assert bundle.platform_account_id == "google-sub-123"
    assert bundle.platform_email == "user@gmail.com"
    assert "gmail.readonly" in " ".join(bundle.granted_scopes)


@pytest.mark.asyncio
async def test_exchange_auth_code_auth_error_raises(connector):
    bad_resp = _mock_response(401, {"error": "invalid_client"})
    mock_client = _mock_client(post_response=bad_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(GmailAuthError):
            await connector.exchange_auth_code("bad-code", "http://localhost/cb")


# ── refresh_access_token ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_access_token_success(connector):
    refresh_resp = _mock_response(200, {
        "access_token": "ya29.new-access",
        "expires_in": 3600,
        "scope": "openid",
    })
    mock_client = _mock_client(post_response=refresh_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        bundle = await connector.refresh_access_token("1//old-refresh")

    assert bundle.access_token == "ya29.new-access"
    # Old refresh token kept when Google doesn't return a new one
    assert bundle.refresh_token == "1//old-refresh"


@pytest.mark.asyncio
async def test_refresh_access_token_failure_raises(connector):
    bad_resp = _mock_response(400, {"error": "invalid_grant"})
    mock_client = _mock_client(post_response=bad_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(Exception):
            await connector.refresh_access_token("revoked-token")


# ── revoke_tokens ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_revoke_tokens_is_non_fatal(connector):
    bad_resp = _mock_response(400, {"error": "invalid_token"})
    mock_client = _mock_client(post_response=bad_resp)
    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        await connector.revoke_tokens("some-token")  # should not raise


# ── fetch_page ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_page_returns_messages(connector):
    list_resp = _mock_response(200, _make_threads_list(["thr-1"]))
    thread_resp = _mock_response(200, _make_thread("thr-1"))
    mock_client = _mock_client(list_resp, thread_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_page(
            "token", None, FetchOptions(folders=["inbox"])
        )

    assert len(result.messages) == 1
    assert result.messages[0].platform_thread_id == "thr-1"


@pytest.mark.asyncio
async def test_fetch_page_returns_next_cursor(connector):
    list_resp = _mock_response(200, _make_threads_list(["thr-1"], next_page="page2tok"))
    thread_resp = _mock_response(200, _make_thread("thr-1"))
    mock_client = _mock_client(list_resp, thread_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_page("token", None, FetchOptions(folders=["inbox"]))

    assert result.next_cursor == "page2tok"


@pytest.mark.asyncio
async def test_fetch_page_last_page_has_no_cursor(connector):
    list_resp = _mock_response(200, _make_threads_list(["thr-1"]))  # no nextPageToken
    thread_resp = _mock_response(200, _make_thread("thr-1"))
    mock_client = _mock_client(list_resp, thread_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_page("token", None, FetchOptions(folders=["inbox"]))

    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_fetch_page_tracks_highest_history_id(connector):
    list_resp = _mock_response(200, _make_threads_list(["thr-1", "thr-2"]))
    thread1 = _make_thread("thr-1")
    thread1["historyId"] = "5000"
    thread2 = _make_thread("thr-2")
    thread2["historyId"] = "9000"
    mock_client = _mock_client(list_resp, _mock_response(200, thread1), _mock_response(200, thread2))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_page("token", None, FetchOptions(folders=["sent"]))

    assert result.sync_checkpoint == "9000"


@pytest.mark.asyncio
async def test_fetch_page_passes_cursor_to_api(connector):
    list_resp = _mock_response(200, _make_threads_list([]))
    mock_client = _mock_client(list_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        await connector.fetch_page("tok", "page2tok", FetchOptions(folders=["inbox"]))

    call_params = mock_client.get.call_args[1].get("params", {})
    assert call_params.get("pageToken") == "page2tok"


@pytest.mark.asyncio
async def test_fetch_page_applies_inbox_label_filter(connector):
    list_resp = _mock_response(200, _make_threads_list([]))
    mock_client = _mock_client(list_resp)

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        await connector.fetch_page("tok", None, FetchOptions(folders=["inbox"]))

    params = mock_client.get.call_args[1].get("params", {})
    assert params.get("labelIds") == "INBOX"


@pytest.mark.asyncio
async def test_fetch_page_401_raises_auth_error(connector):
    mock_client = _mock_client(_mock_response(401, {}))
    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(GmailAuthError):
            await connector.fetch_page("expired", None, FetchOptions(folders=["inbox"]))


# ── fetch_changes ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_changes_returns_mutations(connector):
    history = _make_history(
        added=[("msg-new", "thr-1")],
        deleted=["msg-old"],
        labels_added=[("msg-2", ["IMPORTANT"])],
        labels_removed=[("msg-3", ["UNREAD"])],
        new_history_id="2000",
    )
    mock_client = _mock_client(_mock_response(200, history))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_changes("token", "1000")

    types = [m.type for m in result.mutations]
    assert "messageAdded" in types
    assert "messageDeleted" in types
    assert "labelsChanged" in types
    assert result.new_checkpoint == "2000"


@pytest.mark.asyncio
async def test_fetch_changes_message_added_fields(connector):
    history = _make_history(added=[("msg-x", "thr-y")])
    mock_client = _mock_client(_mock_response(200, history))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_changes("token", "1000")

    added = next(m for m in result.mutations if isinstance(m, MessageAddedMutation))
    assert added.platform_message_id == "msg-x"
    assert added.platform_thread_id == "thr-y"


@pytest.mark.asyncio
async def test_fetch_changes_empty_history_returns_empty_mutations(connector):
    history = {"history": [], "historyId": "1500"}
    mock_client = _mock_client(_mock_response(200, history))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_changes("token", "1000")

    assert result.mutations == []
    assert result.new_checkpoint == "1500"


@pytest.mark.asyncio
async def test_fetch_changes_404_raises_checkpoint_expired(connector):
    mock_client = _mock_client(_mock_response(404, {"error": "invalid_history_id"}))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(CheckpointExpiredError):
            await connector.fetch_changes("token", "expired-checkpoint")


@pytest.mark.asyncio
async def test_fetch_changes_labels_changed_fields(connector):
    history = _make_history(
        labels_added=[("msg-1", ["IMPORTANT"])],
        labels_removed=[("msg-2", ["UNREAD"])],
    )
    mock_client = _mock_client(_mock_response(200, history))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_changes("token", "1000")

    label_mutations = [m for m in result.mutations if isinstance(m, LabelsChangedMutation)]
    assert len(label_mutations) == 2
    added_event = next(m for m in label_mutations if "IMPORTANT" in m.labels_added)
    assert added_event.labels_removed == ()
    removed_event = next(m for m in label_mutations if "UNREAD" in m.labels_removed)
    assert removed_event.labels_added == ()


# ── fetch_message ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_message_parses_correctly(connector):
    msg = _make_message(
        msg_id="msg-abc",
        thread_id="thr-xyz",
        label_ids=["INBOX", "UNREAD"],
        subject="Important email",
        from_addr="Alice <alice@example.com>",
        body="Hello from Alice",
    )
    mock_client = _mock_client(_mock_response(200, msg))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_message("token", "msg-abc")

    assert result.platform_message_id == "msg-abc"
    assert result.platform_thread_id == "thr-xyz"
    assert result.subject == "Important email"
    assert result.from_email == "alice@example.com"
    assert result.from_name == "Alice"
    assert result.body_plain == "Hello from Alice"
    assert result.folder == "inbox"
    assert result.is_sent_by_user is False


@pytest.mark.asyncio
async def test_fetch_message_sent_by_user_flag(connector):
    msg = _make_message(label_ids=["SENT"])
    mock_client = _mock_client(_mock_response(200, msg))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_message("token", "msg-1")

    assert result.is_sent_by_user is True
    assert result.folder == "sent"


@pytest.mark.asyncio
async def test_fetch_message_401_raises(connector):
    mock_client = _mock_client(_mock_response(401, {}))
    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(GmailAuthError):
            await connector.fetch_message("expired", "msg-1")


# ── fetch_thread ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_thread_returns_all_messages(connector):
    thread = _make_thread("thr-1", messages=[
        _make_message("msg-1", "thr-1"),
        _make_message("msg-2", "thr-1"),
    ])
    mock_client = _mock_client(_mock_response(200, thread))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_thread("token", "thr-1")

    assert result.platform_thread_id == "thr-1"
    assert len(result.messages) == 2


@pytest.mark.asyncio
async def test_fetch_thread_builds_participants(connector):
    thread = _make_thread("thr-1", messages=[
        _make_message("msg-1", "thr-1", from_addr="alice@example.com"),
        _make_message("msg-2", "thr-1", from_addr="bob@example.com"),
    ])
    mock_client = _mock_client(_mock_response(200, thread))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_thread("token", "thr-1")

    emails = {p.email for p in result.participants}
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails


@pytest.mark.asyncio
async def test_fetch_thread_subject_from_first_message(connector):
    thread = _make_thread("thr-1", messages=[
        _make_message("msg-1", "thr-1", subject="First subject"),
        _make_message("msg-2", "thr-1", subject="Re: First subject"),
    ])
    mock_client = _mock_client(_mock_response(200, thread))

    with patch("app.connectors.gmail.connector.httpx.AsyncClient", return_value=mock_client):
        result = await connector.fetch_thread("token", "thr-1")

    assert result.subject == "First subject"


# ── get_rate_limit_state ──────────────────────────────────────────────────────

def test_get_rate_limit_state_returns_rate_limit_state(connector):
    state = connector.get_rate_limit_state("conn-1")
    assert isinstance(state, RateLimitState)
    assert state.quota_remaining > 0
    assert state.quota_per_second == 200


def test_get_rate_limit_state_per_connection_independent(connector):
    s1 = connector.get_rate_limit_state("conn-aaa")
    s2 = connector.get_rate_limit_state("conn-bbb")
    # Both start full
    assert s1.quota_remaining == s2.quota_remaining


# ── Registry integration ──────────────────────────────────────────────────────

def test_setup_connectors_registers_gmail():
    from app.connectors import setup_connectors
    from app.connectors.base import get_connector_class

    setup_connectors()
    cls = get_connector_class(PlatformType.GMAIL)
    assert cls is GmailConnector


def test_registered_gmail_connector_can_be_instantiated():
    from app.connectors import setup_connectors
    from app.connectors.base import get_connector_class

    setup_connectors()
    cls = get_connector_class(PlatformType.GMAIL)
    instance = cls()
    assert instance.platform == PlatformType.GMAIL
