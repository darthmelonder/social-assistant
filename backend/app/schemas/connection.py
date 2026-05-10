from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    platform_email: str | None
    status: str
    last_synced_at: datetime | None
    last_sync_error: str | None
    granted_scopes: list[str]
