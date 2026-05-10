from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform_message_id: str
    from_email: str
    from_name: str | None
    to_emails: list[str]
    cc_emails: list[str]
    subject: str | None
    body_plain: str | None
    snippet: str | None
    internal_date: datetime
    folder: str
    labels: list[str]
    is_sent_by_user: bool
    has_attachments: bool


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    priority: str
    priority_confidence: float | None
    summary: str
    action_items: list[dict]
    requires_reply: bool
    sentiment: str | None


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_line: str | None
    body_plain: str
    body_html: str | None
    tone_used: str | None
    status: str
    regeneration_count: int


class ThreadSummary(BaseModel):
    """Lightweight thread projection for the priority inbox list."""
    id: uuid.UUID
    subject: str | None
    snippet: str | None
    last_message_at: datetime | None
    is_unread: bool
    participants: list[dict]
    # From current analysis (None if not yet triaged)
    priority: str | None
    summary: str | None
    action_items: list[dict]
    requires_reply: bool
    # From pending draft (None if no draft)
    draft_status: str | None


class ThreadDetail(BaseModel):
    """Full thread response including messages, analysis, and latest draft."""
    id: uuid.UUID
    subject: str | None
    snippet: str | None
    last_message_at: datetime | None
    is_unread: bool
    participants: list[dict]
    messages: list[MessageOut]
    analysis: AnalysisOut | None
    draft: DraftOut | None


class ThreadListResponse(BaseModel):
    threads: list[ThreadSummary]
    next_cursor: str | None


class ThreadPriorityPatch(BaseModel):
    """Payload for manually overriding a thread's priority."""
    priority_override: str
