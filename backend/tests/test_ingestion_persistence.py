"""Unit tests for ingestion persistence helpers.

All DB operations use AsyncMock — no real DB needed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.connectors.types import RawMessage
from app.models.enums import MessageFolder, PlatformType
from app.workers.ingestion.persistence import (
    _build_participants,
    _folder_from_labels,
    mark_sync_job_complete,
    mark_sync_job_failed,
    mark_sync_job_running,
    soft_delete_message,
    soft_delete_thread,
    update_connection_checkpoint,
    update_message_labels,
    update_sync_job_cursor,
    upsert_thread_with_messages,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

CONN_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
THREAD_ID = uuid.uuid4()
JOB_ID = uuid.uuid4()


def _make_raw_message(
    msg_id: str = "msg-1",
    thread_id: str = "thr-1",
    labels: list[str] | None = None,
    from_email: str = "sender@example.com",
    from_name: str | None = "Sender",
    to_emails: list[str] | None = None,
    subject: str = "Test",
    body: str = "Hello",
    is_sent: bool = False,
    internal_date: datetime | None = None,
) -> RawMessage:
    return RawMessage(
        platform_message_id=msg_id,
        platform_thread_id=thread_id,
        from_email=from_email,
        from_name=from_name,
        to_emails=to_emails or ["me@example.com"],
        cc_emails=[],
        subject=subject,
        body_plain=body,
        body_html=None,
        snippet=body[:20],
        internal_date=internal_date or datetime(2026, 1, 1, tzinfo=timezone.utc),
        labels=labels or ["INBOX", "UNREAD"],
        folder="inbox",
        has_attachments=False,
        attachment_metadata=[],
        is_sent_by_user=is_sent,
        raw_headers={"From": from_email},
    )


def _mock_db(existing=None) -> AsyncMock:
    """Build a mock AsyncSession."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute.return_value = result
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


# ── _folder_from_labels ────────────────────────────────────────────────────────

def test_folder_inbox():
    assert _folder_from_labels(["INBOX", "UNREAD"]) == MessageFolder.INBOX

def test_folder_sent():
    assert _folder_from_labels(["SENT"]) == MessageFolder.SENT

def test_folder_spam():
    assert _folder_from_labels(["SPAM"]) == MessageFolder.SPAM

def test_folder_trash():
    assert _folder_from_labels(["TRASH"]) == MessageFolder.TRASH

def test_folder_draft():
    assert _folder_from_labels(["DRAFT"]) == MessageFolder.DRAFT

def test_folder_other():
    assert _folder_from_labels(["CATEGORY_UPDATES"]) == MessageFolder.OTHER


# ── _build_participants ───────────────────────────────────────────────────────

def test_build_participants_includes_sender():
    msgs = [_make_raw_message(from_email="alice@example.com", from_name="Alice")]
    participants = _build_participants(msgs)
    emails = {p["email"] for p in participants}
    assert "alice@example.com" in emails


def test_build_participants_includes_recipients():
    msgs = [_make_raw_message(to_emails=["bob@example.com"])]
    participants = _build_participants(msgs)
    emails = {p["email"] for p in participants}
    assert "bob@example.com" in emails


def test_build_participants_deduplicates():
    msgs = [
        _make_raw_message("msg-1", from_email="alice@a.com"),
        _make_raw_message("msg-2", from_email="alice@a.com"),
    ]
    participants = _build_participants(msgs)
    alice_entries = [p for p in participants if p["email"] == "alice@a.com"]
    assert len(alice_entries) == 1


def test_build_participants_sent_message_marks_sender_role():
    msgs = [_make_raw_message(is_sent=True, from_email="me@example.com")]
    participants = _build_participants(msgs)
    me = next(p for p in participants if p["email"] == "me@example.com")
    assert me["role"] == "sender"


# ── upsert_thread_with_messages ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_creates_new_thread():
    db = _mock_db(existing=None)
    msgs = [_make_raw_message()]

    await upsert_thread_with_messages(db, msgs, CONN_ID, USER_ID)

    db.add.assert_called()
    added_obj = db.add.call_args_list[0][0][0]
    from app.models.thread import Thread
    assert isinstance(added_obj, Thread)


@pytest.mark.asyncio
async def test_upsert_new_thread_sets_correct_fields():
    db = _mock_db(existing=None)
    msg = _make_raw_message(
        thread_id="thr-x",
        subject="My subject",
        labels=["INBOX", "UNREAD"],
    )

    await upsert_thread_with_messages(db, [msg], CONN_ID, USER_ID)

    added_thread = db.add.call_args_list[0][0][0]
    assert added_thread.platform_thread_id == "thr-x"
    assert added_thread.subject == "My subject"
    assert added_thread.is_unread is True
    assert added_thread.is_in_inbox is True


@pytest.mark.asyncio
async def test_upsert_updates_existing_thread():
    from app.models.thread import Thread
    existing = MagicMock(spec=Thread)
    existing.id = THREAD_ID
    existing.deleted_at = None

    # Two execute calls: Thread lookup, then Message lookup
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = existing
    msg_result = MagicMock()
    msg_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [thread_result, msg_result]
    db.flush = AsyncMock()
    db.add = MagicMock()

    msg = _make_raw_message(body="new snippet body text")
    await upsert_thread_with_messages(db, [msg], CONN_ID, USER_ID)

    assert existing.snippet == "new snippet body tex"  # body[:20]
    assert existing.message_count == 1


@pytest.mark.asyncio
async def test_upsert_raises_on_empty_messages():
    db = _mock_db()
    with pytest.raises(ValueError, match="empty"):
        await upsert_thread_with_messages(db, [], CONN_ID, USER_ID)


@pytest.mark.asyncio
async def test_upsert_creates_new_message():
    db = _mock_db(existing=None)
    msgs = [_make_raw_message(msg_id="msg-new")]

    await upsert_thread_with_messages(db, msgs, CONN_ID, USER_ID)

    from app.models.message import Message
    added_msgs = [c[0][0] for c in db.add.call_args_list if isinstance(c[0][0], Message)]
    assert len(added_msgs) == 1
    assert added_msgs[0].platform_message_id == "msg-new"


@pytest.mark.asyncio
async def test_upsert_updates_existing_message_labels():
    from app.models.thread import Thread
    from app.models.message import Message

    existing_thread = MagicMock(spec=Thread)
    existing_thread.id = THREAD_ID
    existing_msg = MagicMock(spec=Message)
    existing_msg.labels = ["INBOX"]

    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalar_one_or_none.return_value = existing_thread
    msg_result = MagicMock()
    msg_result.scalar_one_or_none.return_value = existing_msg
    db.execute.side_effect = [thread_result, msg_result]
    db.flush = AsyncMock()
    db.add = MagicMock()

    msg = _make_raw_message(labels=["INBOX", "IMPORTANT"])
    await upsert_thread_with_messages(db, [msg], CONN_ID, USER_ID)

    assert "IMPORTANT" in existing_msg.labels


@pytest.mark.asyncio
async def test_upsert_returns_thread_uuid():
    db = _mock_db(existing=None)
    msgs = [_make_raw_message()]
    result = await upsert_thread_with_messages(db, msgs, CONN_ID, USER_ID)
    assert isinstance(result, uuid.UUID)


# ── soft_delete_message ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_soft_delete_message_executes_update():
    db = AsyncMock()
    db.execute.return_value = MagicMock()

    await soft_delete_message(db, "msg-1", CONN_ID)

    db.execute.assert_called_once()


# ── soft_delete_thread ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_soft_delete_thread_marks_thread_and_messages():
    from app.models.thread import Thread
    existing_thread = MagicMock(spec=Thread)
    existing_thread.id = THREAD_ID
    existing_thread.deleted_at = None

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_thread
    db.execute.return_value = result

    await soft_delete_thread(db, "thr-1", CONN_ID)

    assert existing_thread.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_delete_thread_no_op_when_not_found():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    await soft_delete_thread(db, "nonexistent", CONN_ID)  # should not raise


# ── update_message_labels ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_message_labels_adds_and_removes():
    from app.models.message import Message
    existing_msg = MagicMock(spec=Message)
    existing_msg.labels = ["INBOX", "UNREAD"]

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_msg
    db.execute.return_value = result

    await update_message_labels(db, "msg-1", CONN_ID, ("IMPORTANT",), ("UNREAD",))

    assert "IMPORTANT" in existing_msg.labels
    assert "UNREAD" not in existing_msg.labels
    assert "INBOX" in existing_msg.labels  # unchanged


@pytest.mark.asyncio
async def test_update_message_labels_no_op_when_not_found():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    # Should not raise even though message doesn't exist
    await update_message_labels(db, "unknown", CONN_ID, ("IMPORTANT",), ())


# ── Sync job state ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_sync_job_running_calls_execute():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    await mark_sync_job_running(db, JOB_ID)
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_sync_job_cursor_calls_execute():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    await update_sync_job_cursor(db, JOB_ID, "page-token-2", 50)
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_mark_sync_job_complete_calls_execute():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    await mark_sync_job_complete(db, JOB_ID, 150)
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_mark_sync_job_failed_calls_execute():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    await mark_sync_job_failed(db, JOB_ID, "Something went wrong", error_code="E001")
    db.execute.assert_called_once()


# ── Connection checkpoint ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_connection_checkpoint_calls_execute():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    await update_connection_checkpoint(db, CONN_ID, "99999")
    db.execute.assert_called_once()
