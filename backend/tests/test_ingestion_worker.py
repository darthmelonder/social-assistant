"""Unit tests for the Ingestion Worker core logic.

Tests call run_full_sync / run_incremental_sync directly (not the ARQ wrappers)
so they need no ARQ context, no Redis, and no real DB.

All external calls (connector, persistence helpers, token service) are patched
at the worker module level.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.connectors.types import (
    CheckpointExpiredError,
    FetchChangesResult,
    FetchPageResult,
    LabelsChangedMutation,
    MessageAddedMutation,
    MessageDeletedMutation,
    RawMessage,
    ThreadDeletedMutation,
)
from app.workers.ingestion.worker import _group_by_thread, run_full_sync, run_incremental_sync

# ── Fixtures ──────────────────────────────────────────────────────────────────

CONN_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
JOB_ID  = uuid.uuid4()
TOKEN   = "ya29.test-access-token"


def _conn(history_id: str | None = "12345") -> MagicMock:
    c = MagicMock()
    c.id = CONN_ID
    c.user_id = USER_ID
    c.last_history_id = history_id
    c.messages_processed = 0
    return c


def _job(cursor: str | None = None, messages_processed: int = 0) -> MagicMock:
    j = MagicMock()
    j.id = JOB_ID
    j.cursor = cursor
    j.messages_processed = messages_processed
    return j


def _raw_msg(msg_id: str = "msg-1", thread_id: str = "thr-1") -> RawMessage:
    return RawMessage(
        platform_message_id=msg_id,
        platform_thread_id=thread_id,
        from_email="a@b.com",
        from_name=None,
        to_emails=[],
        cc_emails=[],
        subject="Test",
        body_plain="Hello",
        body_html=None,
        snippet="Hello",
        internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        labels=["INBOX"],
        folder="inbox",
        has_attachments=False,
        attachment_metadata=[],
        is_sent_by_user=False,
        raw_headers={},
    )


def _page(
    messages: list[RawMessage] | None = None,
    next_cursor: str | None = None,
    checkpoint: str = "9999",
) -> FetchPageResult:
    return FetchPageResult(
        messages=messages or [],
        next_cursor=next_cursor,
        sync_checkpoint=checkpoint,
    )


def _changes(
    mutations=None,
    new_checkpoint: str = "20000",
) -> FetchChangesResult:
    return FetchChangesResult(mutations=mutations or [], new_checkpoint=new_checkpoint)


# Patch targets (worker module imports these at function call time)
_W = "app.workers.ingestion.worker"


# ── _group_by_thread ──────────────────────────────────────────────────────────

def test_group_by_thread_single():
    msgs = [_raw_msg("m1", "t1"), _raw_msg("m2", "t1")]
    grouped = _group_by_thread(msgs)
    assert list(grouped.keys()) == ["t1"]
    assert len(grouped["t1"]) == 2


def test_group_by_thread_multiple():
    msgs = [_raw_msg("m1", "t1"), _raw_msg("m2", "t2"), _raw_msg("m3", "t1")]
    grouped = _group_by_thread(msgs)
    assert len(grouped) == 2
    assert len(grouped["t1"]) == 2
    assert len(grouped["t2"]) == 1


def test_group_by_thread_empty():
    assert _group_by_thread([]) == {}


# ── run_full_sync — happy path ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_sync_marks_job_running_first():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.return_value = _page()

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running") as mock_running, \
         patch(f"{_W}.update_sync_job_cursor"), \
         patch(f"{_W}.mark_sync_job_complete"), \
         patch(f"{_W}.update_connection_checkpoint"):
        await run_full_sync(db, _conn(), _job(), connector)

    mock_running.assert_called_once_with(db, JOB_ID)


@pytest.mark.asyncio
async def test_full_sync_marks_job_complete():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.return_value = _page()

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.update_sync_job_cursor"), \
         patch(f"{_W}.mark_sync_job_complete") as mock_complete, \
         patch(f"{_W}.update_connection_checkpoint"):
        await run_full_sync(db, _conn(), _job(), connector)

    mock_complete.assert_called_once()


@pytest.mark.asyncio
async def test_full_sync_upserts_messages():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.return_value = _page([_raw_msg("m1", "t1"), _raw_msg("m2", "t1")])

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.update_sync_job_cursor"), \
         patch(f"{_W}.mark_sync_job_complete"), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.upsert_thread_with_messages") as mock_upsert:
        await run_full_sync(db, _conn(), _job(), connector)

    mock_upsert.assert_called_once()  # both msgs are in same thread → one call
    args = mock_upsert.call_args[0]
    assert len(args[1]) == 2  # raw_messages list has both messages


@pytest.mark.asyncio
async def test_full_sync_groups_messages_by_thread():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.return_value = _page([
        _raw_msg("m1", "t1"),
        _raw_msg("m2", "t2"),
        _raw_msg("m3", "t1"),
    ])

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.update_sync_job_cursor"), \
         patch(f"{_W}.mark_sync_job_complete"), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.upsert_thread_with_messages") as mock_upsert:
        await run_full_sync(db, _conn(), _job(), connector)

    # Two threads → two upsert calls
    assert mock_upsert.call_count == 2


@pytest.mark.asyncio
async def test_full_sync_saves_cursor_after_each_page():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.side_effect = [
        _page([_raw_msg()], next_cursor="page2", checkpoint="5000"),
        _page([], next_cursor=None, checkpoint="6000"),
    ]

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.update_sync_job_cursor") as mock_cursor, \
         patch(f"{_W}.mark_sync_job_complete"), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.upsert_thread_with_messages"):
        await run_full_sync(db, _conn(), _job(), connector)

    # First page: cursor saved as "page2"
    assert mock_cursor.call_args_list[0] == call(db, JOB_ID, "page2", 1)
    # Second page: cursor saved as None (last page)
    assert mock_cursor.call_args_list[1] == call(db, JOB_ID, None, 1)


@pytest.mark.asyncio
async def test_full_sync_updates_checkpoint_from_last_page():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.side_effect = [
        _page([_raw_msg()], next_cursor="p2", checkpoint="5000"),
        _page([], checkpoint="9999"),
    ]

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.update_sync_job_cursor"), \
         patch(f"{_W}.mark_sync_job_complete"), \
         patch(f"{_W}.update_connection_checkpoint") as mock_cp, \
         patch(f"{_W}.upsert_thread_with_messages"):
        await run_full_sync(db, _conn(), _job(), connector)

    mock_cp.assert_called_once_with(db, CONN_ID, "9999")


@pytest.mark.asyncio
async def test_full_sync_commits_after_each_page():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.side_effect = [
        _page([_raw_msg()], next_cursor="p2"),
        _page([]),
    ]

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.update_sync_job_cursor"), \
         patch(f"{_W}.mark_sync_job_complete"), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.upsert_thread_with_messages"):
        await run_full_sync(db, _conn(), _job(), connector)

    # Commits: after mark_running + after page1 + after page2 + after completion = 4
    assert db.commit.call_count == 4


# ── run_full_sync — crash resume ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_sync_resumes_from_saved_cursor():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.return_value = _page()

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.update_sync_job_cursor"), \
         patch(f"{_W}.mark_sync_job_complete"), \
         patch(f"{_W}.update_connection_checkpoint"):
        await run_full_sync(db, _conn(), _job(cursor="saved-page-token"), connector)

    # First fetch_page call must use the saved cursor
    first_call_cursor = connector.fetch_page.call_args_list[0][0][1]
    assert first_call_cursor == "saved-page-token"


@pytest.mark.asyncio
async def test_full_sync_resumes_messages_processed_count():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.return_value = _page([_raw_msg()])

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.update_sync_job_cursor") as mock_cursor, \
         patch(f"{_W}.mark_sync_job_complete"), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.upsert_thread_with_messages"):
        await run_full_sync(db, _conn(), _job(messages_processed=50), connector)

    # 50 existing + 1 new message on this page
    assert mock_cursor.call_args[0][3] == 51


# ── run_full_sync — error handling ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_sync_marks_job_failed_on_connector_error():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.side_effect = RuntimeError("Gmail API down")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.mark_sync_job_failed") as mock_failed, \
         patch(f"{_W}.update_connection_sync_error"):
        with pytest.raises(RuntimeError, match="Gmail API down"):
            await run_full_sync(db, _conn(), _job(), connector)

    mock_failed.assert_called_once()
    assert "Gmail API down" in mock_failed.call_args[0][2]


@pytest.mark.asyncio
async def test_full_sync_marks_connection_error_on_failure():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.side_effect = RuntimeError("timeout")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.mark_sync_job_failed"), \
         patch(f"{_W}.update_connection_sync_error") as mock_conn_err:
        with pytest.raises(RuntimeError):
            await run_full_sync(db, _conn(), _job(), connector)

    mock_conn_err.assert_called_once_with(db, CONN_ID, "timeout")


@pytest.mark.asyncio
async def test_full_sync_reraises_exception():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_page.side_effect = ValueError("unexpected")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.mark_sync_job_running"), \
         patch(f"{_W}.mark_sync_job_failed"), \
         patch(f"{_W}.update_connection_sync_error"):
        with pytest.raises(ValueError, match="unexpected"):
            await run_full_sync(db, _conn(), _job(), connector)


# ── run_incremental_sync — happy path ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_incremental_sync_no_op_when_no_history_id():
    db = AsyncMock()
    connector = AsyncMock()

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN):
        await run_incremental_sync(db, _conn(history_id=None), connector)

    connector.fetch_changes.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_incremental_sync_updates_checkpoint():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_changes.return_value = _changes(new_checkpoint="99999")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_checkpoint") as mock_cp:
        await run_incremental_sync(db, _conn(), connector)

    mock_cp.assert_called_once_with(db, CONN_ID, "99999")


@pytest.mark.asyncio
async def test_incremental_sync_handles_message_added():
    db = AsyncMock()
    connector = AsyncMock()
    mutation = MessageAddedMutation(
        platform_message_id="msg-new", platform_thread_id="thr-1"
    )
    connector.fetch_changes.return_value = _changes([mutation])
    connector.fetch_message.return_value = _raw_msg("msg-new", "thr-1")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.upsert_thread_with_messages") as mock_upsert:
        await run_incremental_sync(db, _conn(), connector)

    connector.fetch_message.assert_called_once_with(TOKEN, "msg-new")
    mock_upsert.assert_called_once()


@pytest.mark.asyncio
async def test_incremental_sync_handles_message_deleted():
    db = AsyncMock()
    connector = AsyncMock()
    mutation = MessageDeletedMutation(platform_message_id="msg-old")
    connector.fetch_changes.return_value = _changes([mutation])

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.soft_delete_message") as mock_del:
        await run_incremental_sync(db, _conn(), connector)

    mock_del.assert_called_once_with(db, "msg-old", CONN_ID)


@pytest.mark.asyncio
async def test_incremental_sync_handles_labels_changed():
    db = AsyncMock()
    connector = AsyncMock()
    mutation = LabelsChangedMutation(
        platform_message_id="msg-1",
        labels_added=("IMPORTANT",),
        labels_removed=("UNREAD",),
    )
    connector.fetch_changes.return_value = _changes([mutation])

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.update_message_labels") as mock_labels:
        await run_incremental_sync(db, _conn(), connector)

    mock_labels.assert_called_once_with(
        db, "msg-1", CONN_ID, ("IMPORTANT",), ("UNREAD",)
    )


@pytest.mark.asyncio
async def test_incremental_sync_handles_thread_deleted():
    db = AsyncMock()
    connector = AsyncMock()
    mutation = ThreadDeletedMutation(platform_thread_id="thr-gone")
    connector.fetch_changes.return_value = _changes([mutation])

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.soft_delete_thread") as mock_del:
        await run_incremental_sync(db, _conn(), connector)

    mock_del.assert_called_once_with(db, "thr-gone", CONN_ID)


@pytest.mark.asyncio
async def test_incremental_sync_handles_mixed_mutations():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_changes.return_value = _changes([
        MessageAddedMutation("msg-new", "thr-1"),
        MessageDeletedMutation("msg-old"),
        LabelsChangedMutation("msg-x", ("IMPORTANT",), ()),
    ])
    connector.fetch_message.return_value = _raw_msg("msg-new", "thr-1")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_checkpoint"), \
         patch(f"{_W}.upsert_thread_with_messages") as mock_upsert, \
         patch(f"{_W}.soft_delete_message") as mock_del, \
         patch(f"{_W}.update_message_labels") as mock_labels:
        await run_incremental_sync(db, _conn(), connector)

    mock_upsert.assert_called_once()
    mock_del.assert_called_once()
    mock_labels.assert_called_once()


# ── run_incremental_sync — checkpoint expired ─────────────────────────────────

@pytest.mark.asyncio
async def test_incremental_sync_checkpoint_expired_marks_connection_error():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_changes.side_effect = CheckpointExpiredError("too old")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_sync_error") as mock_err:
        await run_incremental_sync(db, _conn(), connector)

    mock_err.assert_called_once()
    assert "re-sync" in mock_err.call_args[0][2]


@pytest.mark.asyncio
async def test_incremental_sync_checkpoint_expired_does_not_raise():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_changes.side_effect = CheckpointExpiredError("too old")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_sync_error"):
        # Should return gracefully, not raise
        await run_incremental_sync(db, _conn(), connector)


@pytest.mark.asyncio
async def test_incremental_sync_checkpoint_expired_commits():
    db = AsyncMock()
    connector = AsyncMock()
    connector.fetch_changes.side_effect = CheckpointExpiredError("too old")

    with patch(f"{_W}.get_valid_access_token", return_value=TOKEN), \
         patch(f"{_W}.update_connection_sync_error"):
        await run_incremental_sync(db, _conn(), connector)

    db.commit.assert_called_once()


# ── _enqueue_post_sync_jobs ───────────────────────────────────────────────────

def _make_sf(db: AsyncMock) -> MagicMock:
    """Build a session_factory mock whose __call__ returns a proper async ctx manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=cm)


@pytest.mark.asyncio
async def test_enqueue_post_sync_jobs_enqueues_profile_rebuild():
    from app.workers.ingestion.worker import _enqueue_post_sync_jobs

    redis = AsyncMock()
    db = AsyncMock()
    thread_result = MagicMock()
    thread_result.scalars.return_value.all.return_value = []
    db.execute.return_value = thread_result

    conn_id = uuid.uuid4()
    await _enqueue_post_sync_jobs(
        {"redis": redis, "session_factory": _make_sf(db)}, conn_id
    )

    redis.enqueue_job.assert_any_call("profile_rebuild_job", connection_id=str(conn_id))


@pytest.mark.asyncio
async def test_enqueue_post_sync_jobs_enqueues_triage_per_thread():
    from app.workers.ingestion.worker import _enqueue_post_sync_jobs

    redis = AsyncMock()
    db = AsyncMock()
    t1, t2 = uuid.uuid4(), uuid.uuid4()
    thread_result = MagicMock()
    thread_result.scalars.return_value.all.return_value = [t1, t2]
    db.execute.return_value = thread_result

    await _enqueue_post_sync_jobs(
        {"redis": redis, "session_factory": _make_sf(db)}, uuid.uuid4()
    )

    triage_calls = [c for c in redis.enqueue_job.call_args_list if c[0][0] == "triage_job"]
    assert len(triage_calls) == 2


@pytest.mark.asyncio
async def test_enqueue_post_sync_jobs_no_op_without_redis():
    from app.workers.ingestion.worker import _enqueue_post_sync_jobs
    await _enqueue_post_sync_jobs({}, uuid.uuid4())  # should not raise
