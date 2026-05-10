from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_version: int
    voice_summary: str | None
    tone_attributes: list[str]
    attributes: dict
    messages_analyzed_count: int
    analyzed_date_range_start: date | None
    analyzed_date_range_end: date | None
    model_id: str
    model_version: str
    prompt_template_hash: str
    generated_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    status: str
    messages_processed: int
    messages_total: int | None
    error_message: str | None
    triggered_by: str | None
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
