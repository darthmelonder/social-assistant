"""DB persistence helpers for the Ingestion Worker.

All functions accept an open AsyncSession and do NOT commit — the worker
controls transaction boundaries (commit after each page batch so that the
cursor update and message upserts are atomic).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.types import LabelsChangedMutation, MessageDeletedMutation, RawMessage
from app.models.enums import ConnectionStatus, MessageFolder, PlatformType
from app.models.message import Message
from app.models.platform_connection import PlatformConnection
from app.models.sync_job import JobStatus, SyncJob
from app.models.thread import Thread


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _folder_from_labels(label_ids: list[str]) -> MessageFolder:
    label_set = set(label_ids)
    for label, folder in (
        ("INBOX", MessageFolder.INBOX),
        ("SENT", MessageFolder.SENT),
        ("SPAM", MessageFolder.SPAM),
        ("TRASH", MessageFolder.TRASH),
        ("DRAFT", MessageFolder.DRAFT),
    ):
        if label in label_set:
            return folder
    return MessageFolder.OTHER


def _build_participants(messages: list[RawMessage]) -> list[dict]:
    """Build a deduplicated participants list from a thread's messages."""
    seen: dict[str, dict] = {}
    for msg in messages:
        if msg.from_email not in seen:
            seen[msg.from_email] = {
                "email": msg.from_email,
                "name": msg.from_name,
                "role": "sender" if msg.is_sent_by_user else "recipient",
            }
        for addr in msg.to_emails:
            if addr and addr not in seen:
                seen[addr] = {"email": addr, "name": None, "role": "recipient"}
    return list(seen.values())


# ── Thread + Message upsert ───────────────────────────────────────────────────

async def upsert_thread_with_messages(
    db: AsyncSession,
    raw_messages: list[RawMessage],
    connection_id: uuid.UUID,
    user_id: uuid.UUID,
    platform: PlatformType = PlatformType.GMAIL,
) -> uuid.UUID:
    """Upsert one Thread and all its Messages. Returns the Thread's UUID.

    All raw_messages must share the same platform_thread_id.
    Caller is responsible for flushing/committing.
    """
    if not raw_messages:
        raise ValueError("raw_messages must not be empty")

    platform_thread_id = raw_messages[0].platform_thread_id
    sorted_msgs = sorted(raw_messages, key=lambda m: m.internal_date)

    result = await db.execute(
        select(Thread).where(
            Thread.connection_id == connection_id,
            Thread.platform_thread_id == platform_thread_id,
        )
    )
    thread = result.scalar_one_or_none()

    all_labels = sorted({lbl for msg in sorted_msgs for lbl in msg.labels})
    participants = _build_participants(sorted_msgs)
    is_unread = any("UNREAD" in m.labels for m in sorted_msgs)
    is_in_inbox = any("INBOX" in m.labels for m in sorted_msgs)
    has_any_attachment = any(m.has_attachments for m in sorted_msgs)
    now = _now()

    if thread is None:
        thread = Thread(
            id=uuid.uuid4(),
            user_id=user_id,
            connection_id=connection_id,
            platform=platform,
            platform_thread_id=platform_thread_id,
            subject=sorted_msgs[0].subject,
            snippet=sorted_msgs[-1].snippet,
            participants=participants,
            message_count=len(sorted_msgs),
            has_attachments=has_any_attachment,
            labels=all_labels,
            first_message_at=sorted_msgs[0].internal_date,
            last_message_at=sorted_msgs[-1].internal_date,
            is_unread=is_unread,
            is_in_inbox=is_in_inbox,
        )
        db.add(thread)
        await db.flush()  # populate thread.id before FK references below
    else:
        thread.snippet = sorted_msgs[-1].snippet
        thread.participants = participants
        thread.message_count = len(sorted_msgs)
        thread.has_attachments = has_any_attachment
        thread.labels = all_labels
        thread.last_message_at = sorted_msgs[-1].internal_date
        thread.is_unread = is_unread
        thread.is_in_inbox = is_in_inbox
        thread.updated_at = now

    for raw in sorted_msgs:
        await _upsert_message(db, raw, thread.id, connection_id, user_id)

    return thread.id


async def _upsert_message(
    db: AsyncSession,
    raw: RawMessage,
    thread_id: uuid.UUID,
    connection_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(Message).where(
            Message.connection_id == connection_id,
            Message.platform_message_id == raw.platform_message_id,
        )
    )
    existing = result.scalar_one_or_none()
    now = _now()

    attachment_json = (
        [
            {
                "filename": a.filename,
                "mimeType": a.mime_type,
                "size_bytes": a.size_bytes,
                "attachment_id": a.attachment_id,
            }
            for a in raw.attachment_metadata
        ]
        if raw.attachment_metadata
        else None
    )

    if existing is None:
        db.add(Message(
            id=uuid.uuid4(),
            thread_id=thread_id,
            user_id=user_id,
            connection_id=connection_id,
            platform_message_id=raw.platform_message_id,
            from_email=raw.from_email,
            from_name=raw.from_name,
            to_emails=raw.to_emails,
            cc_emails=raw.cc_emails,
            subject=raw.subject,
            body_plain=raw.body_plain,
            body_html=raw.body_html,
            snippet=raw.snippet,
            internal_date=raw.internal_date,
            folder=_folder_from_labels(raw.labels),
            labels=raw.labels,
            has_attachments=raw.has_attachments,
            attachment_metadata=attachment_json,
            headers=raw.raw_headers,
            is_sent_by_user=raw.is_sent_by_user,
        ))
    else:
        # Only mutable fields update — body, headers, from are immutable
        existing.labels = raw.labels
        existing.folder = _folder_from_labels(raw.labels)
        existing.snippet = raw.snippet
        existing.updated_at = now


# ── Incremental sync mutations ────────────────────────────────────────────────

async def soft_delete_message(
    db: AsyncSession,
    platform_message_id: str,
    connection_id: uuid.UUID,
) -> None:
    """Set deleted_at on a message. Idempotent."""
    now = _now()
    await db.execute(
        update(Message)
        .where(
            Message.connection_id == connection_id,
            Message.platform_message_id == platform_message_id,
            Message.deleted_at.is_(None),
        )
        .values(deleted_at=now, updated_at=now)
    )


async def soft_delete_thread(
    db: AsyncSession,
    platform_thread_id: str,
    connection_id: uuid.UUID,
) -> None:
    """Set deleted_at on a thread and all its messages. Idempotent."""
    now = _now()
    result = await db.execute(
        select(Thread).where(
            Thread.connection_id == connection_id,
            Thread.platform_thread_id == platform_thread_id,
        )
    )
    thread = result.scalar_one_or_none()
    if thread and not thread.deleted_at:
        thread.deleted_at = now
        thread.updated_at = now
        await db.execute(
            update(Message)
            .where(Message.thread_id == thread.id, Message.deleted_at.is_(None))
            .values(deleted_at=now, updated_at=now)
        )


async def update_message_labels(
    db: AsyncSession,
    platform_message_id: str,
    connection_id: uuid.UUID,
    labels_added: tuple[str, ...],
    labels_removed: tuple[str, ...],
) -> None:
    """Apply a LabelsChanged mutation to a message's labels array."""
    result = await db.execute(
        select(Message).where(
            Message.connection_id == connection_id,
            Message.platform_message_id == platform_message_id,
        )
    )
    msg = result.scalar_one_or_none()
    if msg is None:
        return  # message not yet ingested — will be picked up on next sync

    current = set(msg.labels or [])
    current.update(labels_added)
    current -= set(labels_removed)
    msg.labels = sorted(current)
    msg.folder = _folder_from_labels(list(current))
    msg.updated_at = _now()


# ── Sync job state ────────────────────────────────────────────────────────────

async def mark_sync_job_running(db: AsyncSession, job_id: uuid.UUID) -> None:
    await db.execute(
        update(SyncJob)
        .where(SyncJob.id == job_id)
        .values(status=JobStatus.RUNNING, started_at=_now())
    )


async def update_sync_job_cursor(
    db: AsyncSession,
    job_id: uuid.UUID,
    cursor: str | None,
    messages_processed: int,
) -> None:
    """Save crash-recovery cursor after each page batch."""
    await db.execute(
        update(SyncJob)
        .where(SyncJob.id == job_id)
        .values(cursor=cursor, messages_processed=messages_processed)
    )


async def mark_sync_job_complete(
    db: AsyncSession,
    job_id: uuid.UUID,
    messages_processed: int,
) -> None:
    await db.execute(
        update(SyncJob)
        .where(SyncJob.id == job_id)
        .values(
            status=JobStatus.COMPLETED,
            completed_at=_now(),
            messages_processed=messages_processed,
            cursor=None,
        )
    )


async def mark_sync_job_failed(
    db: AsyncSession,
    job_id: uuid.UUID,
    error_message: str,
    error_code: str | None = None,
) -> None:
    await db.execute(
        update(SyncJob)
        .where(SyncJob.id == job_id)
        .values(
            status=JobStatus.FAILED,
            completed_at=_now(),
            error_message=error_message,
            error_code=error_code,
        )
    )


# ── Connection state ──────────────────────────────────────────────────────────

async def update_connection_checkpoint(
    db: AsyncSession,
    connection_id: uuid.UUID,
    history_id: str,
) -> None:
    """Persist the new historyId after a successful incremental sync."""
    await db.execute(
        update(PlatformConnection)
        .where(PlatformConnection.id == connection_id)
        .values(
            last_history_id=history_id,
            last_synced_at=_now(),
            status=ConnectionStatus.ACTIVE,
            last_sync_error=None,
        )
    )


async def update_connection_sync_error(
    db: AsyncSession,
    connection_id: uuid.UUID,
    error: str,
) -> None:
    await db.execute(
        update(PlatformConnection)
        .where(PlatformConnection.id == connection_id)
        .values(status=ConnectionStatus.ERROR, last_sync_error=error)
    )
