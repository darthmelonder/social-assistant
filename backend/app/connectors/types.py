"""Platform-agnostic data types shared across all connectors.

These types are the boundary between the platform connectors and the rest
of the app. They carry no SQLAlchemy or DB concerns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Union


# ── Folder normalization ──────────────────────────────────────────────────────

FolderType = Literal["inbox", "sent", "draft", "spam", "trash", "other"]


# ── Core message / thread types ───────────────────────────────────────────────

@dataclass(frozen=True)
class Participant:
    email: str
    name: str | None
    role: Literal["sender", "recipient", "cc", "bcc"]


@dataclass(frozen=True)
class AttachmentMeta:
    filename: str
    mime_type: str
    size_bytes: int
    attachment_id: str


@dataclass
class RawMessage:
    """One email message, fully normalized from platform wire format."""
    platform_message_id: str
    platform_thread_id: str
    from_email: str
    from_name: str | None
    to_emails: list[str]
    cc_emails: list[str]
    subject: str | None
    body_plain: str | None       # UTF-8, decoded from MIME
    body_html: str | None        # raw HTML (sanitized elsewhere)
    snippet: str | None
    internal_date: datetime
    labels: list[str]            # platform-native label strings
    folder: FolderType
    has_attachments: bool
    attachment_metadata: list[AttachmentMeta]
    is_sent_by_user: bool
    raw_headers: dict[str, str]


@dataclass
class RawThread:
    """One email thread with all its messages."""
    platform_thread_id: str
    subject: str | None
    messages: list[RawMessage]
    participants: list[Participant]


# ── OAuth token bundle ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TokenBundle:
    """Tokens returned from OAuth exchange or refresh — not yet encrypted."""
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    granted_scopes: list[str]
    platform_account_id: str    # Google sub, phone number, Slack user ID, etc.
    platform_email: str | None


# ── Sync operation types ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class FetchOptions:
    folders: list[FolderType]
    max_results: int = 100
    date_from: datetime | None = None


@dataclass
class FetchPageResult:
    messages: list[RawMessage]
    next_cursor: str | None     # None means this is the last page
    sync_checkpoint: str        # opaque — historyId for Gmail; saved to platform_connections


@dataclass
class FetchChangesResult:
    mutations: list[PlatformMutation]
    new_checkpoint: str


# ── Incremental sync mutations ────────────────────────────────────────────────

@dataclass(frozen=True)
class MessageAddedMutation:
    platform_message_id: str
    platform_thread_id: str
    type: str = field(default="messageAdded", init=False)


@dataclass(frozen=True)
class MessageDeletedMutation:
    platform_message_id: str
    type: str = field(default="messageDeleted", init=False)


@dataclass(frozen=True)
class LabelsChangedMutation:
    platform_message_id: str
    labels_added: tuple[str, ...]
    labels_removed: tuple[str, ...]
    type: str = field(default="labelsChanged", init=False)


@dataclass(frozen=True)
class ThreadDeletedMutation:
    platform_thread_id: str
    type: str = field(default="threadDeleted", init=False)


PlatformMutation = Union[
    MessageAddedMutation,
    MessageDeletedMutation,
    LabelsChangedMutation,
    ThreadDeletedMutation,
]


# ── Rate limit state ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RateLimitState:
    quota_remaining: float
    quota_per_second: int
    retry_after_ms: int | None   # None = not currently throttled


# ── Errors ────────────────────────────────────────────────────────────────────

class CheckpointExpiredError(Exception):
    """Raised by fetch_changes when the stored historyId is too old (> ~30 days).

    Caller must fall back to a full re-sync and obtain a fresh checkpoint.
    """
