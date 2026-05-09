"""Unit tests for ORM models and enums.

All tests are pure Python — no DB connection required.

Note on defaults: SQLAlchemy mapped_column(default=X) applies at INSERT time
(DML-level), not at Python instantiation. Tests here verify column *configuration*
via sqlalchemy.inspect() rather than instantiation values. DB-level default
behaviour is covered in integration tests (Milestone 10 dry-run).
"""
import uuid

import pytest
from sqlalchemy import inspect as sa_inspect

from app.models.enums import (
    ConnectionStatus,
    DraftStatus,
    JobStatus,
    JobType,
    MessageFolder,
    PlatformType,
    PriorityLevel,
    SentimentType,
)


# ── Enum value tests ──────────────────────────────────────────────────────────

class TestPlatformType:
    def test_values(self):
        assert PlatformType.GMAIL == "gmail"
        assert PlatformType.WHATSAPP == "whatsapp"
        assert PlatformType.SLACK == "slack"
        assert PlatformType.OUTLOOK == "outlook"

    def test_from_string(self):
        assert PlatformType("gmail") is PlatformType.GMAIL


class TestConnectionStatus:
    def test_all_values(self):
        assert {s.value for s in ConnectionStatus} == {
            "active", "error", "revoked", "syncing", "pending"
        }


class TestPriorityLevel:
    def test_all_values(self):
        assert {s.value for s in PriorityLevel} == {
            "urgent", "important", "maybe", "skip"
        }


class TestDraftStatus:
    def test_all_values(self):
        assert {s.value for s in DraftStatus} == {
            "pending_review", "approved", "rejected", "copied", "superseded"
        }


class TestJobType:
    def test_all_values(self):
        assert {s.value for s in JobType} == {
            "full_sync", "incremental_sync", "profile_rebuild", "triage", "draft_generate"
        }


class TestJobStatus:
    def test_all_values(self):
        assert {s.value for s in JobStatus} == {
            "queued", "running", "completed", "failed", "cancelled", "retrying"
        }


class TestMessageFolder:
    def test_all_values(self):
        assert {s.value for s in MessageFolder} == {
            "inbox", "sent", "draft", "spam", "trash", "other"
        }


# ── Model table name tests ────────────────────────────────────────────────────

def test_table_names():
    from app.models import (
        Draft, Message, PlatformConnection, SyncJob,
        Thread, ThreadAnalysis, User, UserProfile,
    )
    assert User.__tablename__ == "users"
    assert PlatformConnection.__tablename__ == "platform_connections"
    assert Thread.__tablename__ == "threads"
    assert Message.__tablename__ == "messages"
    assert ThreadAnalysis.__tablename__ == "thread_analyses"
    assert Draft.__tablename__ == "drafts"
    assert UserProfile.__tablename__ == "user_profiles"
    assert SyncJob.__tablename__ == "sync_jobs"


# ── Column configuration tests (via inspect) ──────────────────────────────────

class TestUserColumns:
    def setup_method(self):
        from app.models.user import User
        self.cols = {c.key: c for c in sa_inspect(User).columns}

    def test_id_is_primary_key_with_uuid_default(self):
        col = self.cols["id"]
        assert col.primary_key is True
        assert col.default is not None  # uuid4 callable default

    def test_email_is_not_nullable_and_unique(self):
        col = self.cols["email"]
        assert col.nullable is False
        assert col.unique is True

    def test_is_active_is_not_nullable_with_default(self):
        col = self.cols["is_active"]
        assert col.nullable is False
        assert col.default is not None

    def test_deleted_at_is_nullable(self):
        assert self.cols["deleted_at"].nullable is True

    def test_display_name_is_nullable(self):
        assert self.cols["display_name"].nullable is True


class TestPlatformConnectionColumns:
    def setup_method(self):
        from app.models.platform_connection import PlatformConnection
        self.cols = {c.key: c for c in sa_inspect(PlatformConnection).columns}

    def test_encrypted_fields_are_not_nullable(self):
        assert self.cols["encrypted_access_token"].nullable is False
        assert self.cols["token_iv"].nullable is False
        assert self.cols["token_tag"].nullable is False
        assert self.cols["token_key_id"].nullable is False

    def test_refresh_token_is_nullable(self):
        # Some platforms may not issue refresh tokens
        assert self.cols["encrypted_refresh_token"].nullable is True

    def test_status_has_pending_default(self):
        col = self.cols["status"]
        assert col.nullable is False
        assert col.default is not None

    def test_last_history_id_is_nullable(self):
        assert self.cols["last_history_id"].nullable is True


class TestThreadColumns:
    def setup_method(self):
        from app.models.thread import Thread
        self.cols = {c.key: c for c in sa_inspect(Thread).columns}

    def test_required_columns_not_nullable(self):
        for name in ("user_id", "connection_id", "platform", "platform_thread_id"):
            assert self.cols[name].nullable is False, f"{name} should not be nullable"

    def test_optional_columns_nullable(self):
        for name in ("subject", "snippet", "first_message_at", "last_message_at", "deleted_at"):
            assert self.cols[name].nullable is True, f"{name} should be nullable"

    def test_message_count_has_default(self):
        assert self.cols["message_count"].default is not None


class TestMessageColumns:
    def setup_method(self):
        from app.models.message import Message
        self.cols = {c.key: c for c in sa_inspect(Message).columns}

    def test_body_columns_are_nullable(self):
        for name in ("body_plain", "body_html", "snippet"):
            assert self.cols[name].nullable is True

    def test_from_email_not_nullable(self):
        assert self.cols["from_email"].nullable is False

    def test_internal_date_not_nullable(self):
        assert self.cols["internal_date"].nullable is False

    def test_is_sent_by_user_has_default(self):
        assert self.cols["is_sent_by_user"].default is not None


class TestThreadAnalysisColumns:
    def setup_method(self):
        from app.models.thread_analysis import ThreadAnalysis
        self.cols = {c.key: c for c in sa_inspect(ThreadAnalysis).columns}

    def test_model_provenance_columns_not_nullable(self):
        for name in ("model_id", "model_version", "prompt_template_hash"):
            assert self.cols[name].nullable is False

    def test_token_counts_are_nullable(self):
        for name in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
            assert self.cols[name].nullable is True

    def test_is_current_has_default(self):
        assert self.cols["is_current"].default is not None

    def test_source_fields_not_nullable(self):
        assert self.cols["source_message_ids"].nullable is False
        assert self.cols["source_message_hash"].nullable is False


class TestDraftColumns:
    def setup_method(self):
        from app.models.draft import Draft
        self.cols = {c.key: c for c in sa_inspect(Draft).columns}

    def test_body_plain_not_nullable(self):
        assert self.cols["body_plain"].nullable is False

    def test_optional_fields_nullable(self):
        for name in ("subject_line", "body_html", "user_edited_body", "feedback_note",
                     "reviewed_at", "parent_draft_id", "analysis_id"):
            assert self.cols[name].nullable is True

    def test_status_has_default(self):
        assert self.cols["status"].default is not None

    def test_regeneration_count_has_default(self):
        assert self.cols["regeneration_count"].default is not None


class TestSyncJobColumns:
    def setup_method(self):
        from app.models.sync_job import SyncJob
        self.cols = {c.key: c for c in sa_inspect(SyncJob).columns}

    def test_connection_id_is_nullable(self):
        # Profile rebuild jobs have no associated connection
        assert self.cols["connection_id"].nullable is True

    def test_status_has_default(self):
        assert self.cols["status"].default is not None

    def test_attempt_counters_have_defaults(self):
        assert self.cols["attempt_number"].default is not None
        assert self.cols["max_attempts"].default is not None

    def test_error_fields_nullable(self):
        for name in ("error_code", "error_message", "error_detail", "cursor"):
            assert self.cols[name].nullable is True


# ── Relationship tests ────────────────────────────────────────────────────────

def test_user_relationships():
    from app.models.user import User
    rels = {r.key for r in sa_inspect(User).relationships}
    assert {"platform_connections", "threads", "user_profiles", "sync_jobs"}.issubset(rels)


def test_platform_connection_relationships():
    from app.models.platform_connection import PlatformConnection
    rels = {r.key for r in sa_inspect(PlatformConnection).relationships}
    assert {"user", "threads", "user_profiles", "sync_jobs"}.issubset(rels)


def test_thread_relationships():
    from app.models.thread import Thread
    rels = {r.key for r in sa_inspect(Thread).relationships}
    assert {"user", "connection", "messages", "analyses", "drafts"}.issubset(rels)


def test_draft_self_referential_relationship():
    from app.models.draft import Draft
    rels = {r.key for r in sa_inspect(Draft).relationships}
    assert "parent_draft" in rels


# ── Model instantiation (explicit values only) ────────────────────────────────

def test_user_accepts_explicit_fields():
    from app.models.user import User
    user = User(email="test@example.com", is_active=True, timezone="UTC")
    assert user.email == "test@example.com"
    assert user.is_active is True


def test_platform_connection_accepts_explicit_fields():
    from app.models.platform_connection import PlatformConnection
    conn = PlatformConnection(
        user_id=uuid.uuid4(),
        platform=PlatformType.GMAIL,
        platform_account_id="12345",
        encrypted_access_token=b"enc",
        token_iv=b"iv",
        token_tag=b"tag",
        token_key_id="key-v1",
        token_expires_at=__import__("datetime").datetime(2030, 1, 1),
        status=ConnectionStatus.ACTIVE,
    )
    assert conn.platform == PlatformType.GMAIL
    assert conn.status == ConnectionStatus.ACTIVE


def test_sync_job_accepts_explicit_fields():
    from app.models.sync_job import SyncJob
    job = SyncJob(
        user_id=uuid.uuid4(),
        job_type=JobType.FULL_SYNC,
        status=JobStatus.QUEUED,
    )
    assert job.job_type == JobType.FULL_SYNC
    assert job.status == JobStatus.QUEUED


# ── Base metadata test ────────────────────────────────────────────────────────

def test_all_tables_registered_in_metadata():
    from app.models.base import Base
    import app.models  # noqa: F401

    expected = {
        "users", "platform_connections", "threads", "messages",
        "thread_analyses", "drafts", "user_profiles", "sync_jobs",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))
