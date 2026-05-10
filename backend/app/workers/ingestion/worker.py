"""Ingestion Worker — ARQ background jobs for Gmail sync.

Two jobs:
  full_sync_job      — paginated pull of all threads; crash-resumable via cursor
  incremental_sync_job — applies History API mutations since last checkpoint

The testable core logic lives in run_full_sync / run_incremental_sync.
The ARQ entry points (full_sync_job / incremental_sync_job) are thin wrappers
that obtain a DB session and the right connector, then delegate.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import PlatformConnector
from app.connectors.types import (
    CheckpointExpiredError,
    FetchOptions,
    LabelsChangedMutation,
    MessageAddedMutation,
    MessageDeletedMutation,
    RawMessage,
    ThreadDeletedMutation,
)
from app.models.platform_connection import PlatformConnection
from app.models.sync_job import SyncJob
from app.services.token_service import get_valid_access_token
from app.workers.ingestion.persistence import (
    mark_sync_job_complete,
    mark_sync_job_failed,
    mark_sync_job_running,
    soft_delete_message,
    soft_delete_thread,
    update_connection_checkpoint,
    update_connection_sync_error,
    update_message_labels,
    update_sync_job_cursor,
    upsert_thread_with_messages,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _group_by_thread(messages: list[RawMessage]) -> dict[str, list[RawMessage]]:
    grouped: dict[str, list[RawMessage]] = {}
    for msg in messages:
        grouped.setdefault(msg.platform_thread_id, []).append(msg)
    return grouped


async def _load_connection(db: AsyncSession, connection_id: uuid.UUID) -> PlatformConnection:
    result = await db.execute(
        select(PlatformConnection).where(PlatformConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise ValueError(f"PlatformConnection {connection_id} not found")
    return conn


async def _load_job(db: AsyncSession, job_id: uuid.UUID) -> SyncJob:
    result = await db.execute(select(SyncJob).where(SyncJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise ValueError(f"SyncJob {job_id} not found")
    return job


# ── Core logic (injected deps — fully testable) ───────────────────────────────

async def run_full_sync(
    db: AsyncSession,
    conn: PlatformConnection,
    job: SyncJob,
    connector: PlatformConnector,
) -> None:
    """Full paginated sync.

    Crash-resumable: cursor is saved atomically with each page's messages so
    a restart picks up from the last committed page rather than the beginning.
    """
    await mark_sync_job_running(db, job.id)
    await db.commit()

    access_token = await get_valid_access_token(conn, connector, db)

    options = FetchOptions(folders=["inbox", "sent"], max_results=100)
    cursor: str | None = job.cursor          # None = fresh start; str = crash resume
    messages_processed: int = job.messages_processed or 0
    last_checkpoint: str = conn.last_history_id or "0"

    try:
        while True:
            page = await connector.fetch_page(access_token, cursor, options)
            last_checkpoint = page.sync_checkpoint

            for thread_msgs in _group_by_thread(page.messages).values():
                await upsert_thread_with_messages(db, thread_msgs, conn.id, conn.user_id)

            messages_processed += len(page.messages)

            # Cursor + progress are committed with the messages — atomic crash recovery
            await update_sync_job_cursor(db, job.id, page.next_cursor, messages_processed)
            await db.commit()

            if page.next_cursor is None:
                break
            cursor = page.next_cursor

        await update_connection_checkpoint(db, conn.id, last_checkpoint)
        await mark_sync_job_complete(db, job.id, messages_processed)
        await db.commit()

    except Exception as exc:
        await mark_sync_job_failed(db, job.id, str(exc))
        await update_connection_sync_error(db, conn.id, str(exc))
        await db.commit()
        raise


async def run_incremental_sync(
    db: AsyncSession,
    conn: PlatformConnection,
    connector: PlatformConnector,
) -> None:
    """Incremental sync via Gmail History API.

    If the stored historyId has expired (> ~30 days old), marks the connection
    with an error so the scheduler can enqueue a fresh full sync.
    """
    if not conn.last_history_id:
        return  # full sync hasn't completed yet; nothing to diff against

    access_token = await get_valid_access_token(conn, connector, db)

    try:
        changes = await connector.fetch_changes(access_token, conn.last_history_id)
    except CheckpointExpiredError:
        await update_connection_sync_error(
            db, conn.id, "historyId expired; full re-sync required"
        )
        await db.commit()
        return

    for mutation in changes.mutations:
        if isinstance(mutation, MessageAddedMutation):
            raw_msg = await connector.fetch_message(
                access_token, mutation.platform_message_id
            )
            await upsert_thread_with_messages(db, [raw_msg], conn.id, conn.user_id)

        elif isinstance(mutation, MessageDeletedMutation):
            await soft_delete_message(db, mutation.platform_message_id, conn.id)

        elif isinstance(mutation, LabelsChangedMutation):
            await update_message_labels(
                db,
                mutation.platform_message_id,
                conn.id,
                mutation.labels_added,
                mutation.labels_removed,
            )

        elif isinstance(mutation, ThreadDeletedMutation):
            await soft_delete_thread(db, mutation.platform_thread_id, conn.id)

    await update_connection_checkpoint(db, conn.id, changes.new_checkpoint)
    await db.commit()


# ── ARQ entry points ──────────────────────────────────────────────────────────

async def full_sync_job(ctx: dict, *, connection_id: str, job_id: str) -> None:
    """ARQ job: full paginated sync for one platform connection."""
    from app.connectors.gmail.connector import GmailConnector

    session_factory = ctx["session_factory"]
    async with session_factory() as db:
        conn = await _load_connection(db, uuid.UUID(connection_id))
        job = await _load_job(db, uuid.UUID(job_id))
        await run_full_sync(db, conn, job, GmailConnector())


async def incremental_sync_job(ctx: dict, *, connection_id: str) -> None:
    """ARQ job: incremental History API sync for one platform connection."""
    from app.connectors.gmail.connector import GmailConnector

    session_factory = ctx["session_factory"]
    async with session_factory() as db:
        conn = await _load_connection(db, uuid.UUID(connection_id))
        await run_incremental_sync(db, conn, GmailConnector())
