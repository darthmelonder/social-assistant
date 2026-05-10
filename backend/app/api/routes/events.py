"""Server-Sent Events (SSE) endpoint for real-time UI updates.

The client subscribes once and receives push notifications for:
  thread.analysis_complete  — triage finished for a thread
  draft.ready               — a new draft is available
  sync.progress             — ingestion worker progress update
  sync.complete             — sync job finished

MVP implementation: yields a connection acknowledgment then periodic keepalives.
Full push (Redis pub/sub fan-out) is a post-MVP enhancement.

Browser note: native EventSource does not support custom headers, so the JWT
can be passed via the ?token= query parameter as an alternative to Bearer.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_db
from app.services.jwt_service import InvalidTokenError, decode_access_token

router = APIRouter(tags=["events"])

_KEEPALIVE_INTERVAL = 30  # seconds between keepalive comments


@router.get("/api/v1/events")
async def events_stream(
    token: str | None = Query(default=None, description="JWT for browser EventSource clients"),
    credentials: HTTPAuthorizationCredentials | None = Security(
        HTTPBearer(auto_error=False)
    ),
):
    """SSE stream — subscribe once, receive real-time events.

    Authentication:
      - Authorization: Bearer <jwt>  (standard API clients)
      - ?token=<jwt>                 (browser EventSource, which cannot set headers)
    """
    raw_token = token or (credentials.credentials if credentials else None)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    try:
        payload = decode_access_token(raw_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = str(payload.user_id)

    async def generator():
        # Connection acknowledgment
        yield _event("connected", {"user_id": user_id})
        # Keepalive loop — real events are pushed here via pub/sub in future
        while True:
            await asyncio.sleep(_KEEPALIVE_INTERVAL)
            yield ": keepalive\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # prevent nginx from buffering the stream
            "Connection": "keep-alive",
        },
    )


def _event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
