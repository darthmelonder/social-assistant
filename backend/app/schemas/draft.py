from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DraftUpdateRequest(BaseModel):
    """PATCH body for approving, rejecting, or copying a draft."""
    status: Literal["approved", "rejected", "copied"]
    user_edited_body: str | None = None   # populated if user edited before copying
    feedback_note: str | None = None      # reason for rejection or free-text note


class DraftListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    subject_line: str | None
    body_plain: str
    body_html: str | None
    tone_used: str | None
    status: str
    regeneration_count: int
    generated_at: datetime
    reviewed_at: datetime | None
