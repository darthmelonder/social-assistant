"""Tests for connector data types, mutations, and registry."""
import pytest

from app.connectors.types import (
    CheckpointExpiredError,
    FetchOptions,
    LabelsChangedMutation,
    MessageAddedMutation,
    MessageDeletedMutation,
    Participant,
    RateLimitState,
    RawMessage,
    RawThread,
    ThreadDeletedMutation,
    TokenBundle,
)
from app.models.enums import PlatformType


# ── Mutation type field tests ─────────────────────────────────────────────────

def test_message_added_has_correct_type_field():
    m = MessageAddedMutation(platform_message_id="msg-1", platform_thread_id="thr-1")
    assert m.type == "messageAdded"


def test_message_deleted_has_correct_type_field():
    m = MessageDeletedMutation(platform_message_id="msg-1")
    assert m.type == "messageDeleted"


def test_labels_changed_has_correct_type_field():
    m = LabelsChangedMutation(
        platform_message_id="msg-1",
        labels_added=("IMPORTANT",),
        labels_removed=("UNREAD",),
    )
    assert m.type == "labelsChanged"


def test_thread_deleted_has_correct_type_field():
    m = ThreadDeletedMutation(platform_thread_id="thr-1")
    assert m.type == "threadDeleted"


def test_mutations_are_frozen():
    m = MessageAddedMutation(platform_message_id="x", platform_thread_id="y")
    with pytest.raises((AttributeError, TypeError)):
        m.platform_message_id = "z"  # type: ignore[misc]


# ── Participant ───────────────────────────────────────────────────────────────

def test_participant_stores_all_fields():
    p = Participant(email="a@b.com", name="Alice", role="sender")
    assert p.email == "a@b.com"
    assert p.name == "Alice"
    assert p.role == "sender"


def test_participant_name_can_be_none():
    p = Participant(email="a@b.com", name=None, role="recipient")
    assert p.name is None


# ── FetchOptions ──────────────────────────────────────────────────────────────

def test_fetch_options_defaults():
    opts = FetchOptions(folders=["inbox"])
    assert opts.max_results == 100
    assert opts.date_from is None


def test_fetch_options_multiple_folders():
    opts = FetchOptions(folders=["inbox", "sent"], max_results=50)
    assert opts.max_results == 50
    assert "sent" in opts.folders


# ── RawMessage ────────────────────────────────────────────────────────────────

def test_raw_message_instantiation():
    from datetime import datetime, timezone
    msg = RawMessage(
        platform_message_id="msg-abc",
        platform_thread_id="thr-xyz",
        from_email="sender@example.com",
        from_name="Sender",
        to_emails=["me@example.com"],
        cc_emails=[],
        subject="Hello",
        body_plain="Hi there",
        body_html="<p>Hi there</p>",
        snippet="Hi there",
        internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        labels=["INBOX", "UNREAD"],
        folder="inbox",
        has_attachments=False,
        attachment_metadata=[],
        is_sent_by_user=False,
        raw_headers={"From": "sender@example.com"},
    )
    assert msg.platform_message_id == "msg-abc"
    assert msg.from_email == "sender@example.com"
    assert msg.folder == "inbox"


# ── RawThread ────────────────────────────────────────────────────────────────

def test_raw_thread_instantiation():
    thread = RawThread(
        platform_thread_id="thr-1",
        subject="Test thread",
        messages=[],
        participants=[],
    )
    assert thread.subject == "Test thread"
    assert thread.messages == []


# ── TokenBundle ───────────────────────────────────────────────────────────────

def test_token_bundle_is_frozen():
    from datetime import datetime, timezone
    bundle = TokenBundle(
        access_token="ya29.access",
        refresh_token="1//refresh",
        expires_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        granted_scopes=["gmail.readonly"],
        platform_account_id="sub-123",
        platform_email="user@gmail.com",
    )
    with pytest.raises((AttributeError, TypeError)):
        bundle.access_token = "other"  # type: ignore[misc]


def test_token_bundle_refresh_token_optional():
    from datetime import datetime, timezone
    bundle = TokenBundle(
        access_token="ya29",
        refresh_token=None,
        expires_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        granted_scopes=[],
        platform_account_id="sub",
        platform_email=None,
    )
    assert bundle.refresh_token is None


# ── RateLimitState ────────────────────────────────────────────────────────────

def test_rate_limit_state_fields():
    state = RateLimitState(quota_remaining=150.0, quota_per_second=200, retry_after_ms=None)
    assert state.quota_remaining == 150.0
    assert state.retry_after_ms is None


# ── CheckpointExpiredError ────────────────────────────────────────────────────

def test_checkpoint_expired_error_is_exception():
    with pytest.raises(CheckpointExpiredError):
        raise CheckpointExpiredError("historyId 123 is expired")


# ── Registry ──────────────────────────────────────────────────────────────────

def test_registry_register_and_retrieve():
    from app.connectors.base import (
        PlatformConnector,
        get_connector_class,
        register_connector,
    )

    class _FakeConnector(PlatformConnector):
        @property
        def platform(self): return PlatformType.SLACK
        async def exchange_auth_code(self, *a, **kw): ...
        async def refresh_access_token(self, *a, **kw): ...
        async def revoke_tokens(self, *a, **kw): ...
        async def fetch_page(self, *a, **kw): ...
        async def fetch_changes(self, *a, **kw): ...
        async def fetch_message(self, *a, **kw): ...
        async def fetch_thread(self, *a, **kw): ...
        def get_rate_limit_state(self, *a, **kw): ...

    register_connector(PlatformType.SLACK, _FakeConnector)
    assert get_connector_class(PlatformType.SLACK) is _FakeConnector


def test_registry_unregistered_platform_raises():
    from app.connectors.base import get_connector_class
    with pytest.raises(KeyError, match="whatsapp"):
        get_connector_class(PlatformType.WHATSAPP)


def test_abstract_connector_cannot_be_instantiated():
    from app.connectors.base import PlatformConnector
    with pytest.raises(TypeError):
        PlatformConnector()  # type: ignore[abstract]
