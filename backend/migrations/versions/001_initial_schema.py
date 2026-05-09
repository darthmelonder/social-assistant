"""Initial schema — all tables and indexes

Revision ID: 001
Revises:
Create Date: 2026-05-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────────────
    op.execute(sa.text(
        "CREATE TYPE platform_type AS ENUM ('gmail', 'whatsapp', 'slack', 'outlook')"
    ))
    op.execute(sa.text(
        "CREATE TYPE connection_status AS ENUM ('active', 'error', 'revoked', 'syncing', 'pending')"
    ))
    op.execute(sa.text(
        "CREATE TYPE message_folder AS ENUM ('inbox', 'sent', 'draft', 'spam', 'trash', 'other')"
    ))
    op.execute(sa.text(
        "CREATE TYPE priority_level AS ENUM ('urgent', 'important', 'maybe', 'skip')"
    ))
    op.execute(sa.text(
        "CREATE TYPE sentiment_type AS ENUM ('positive', 'neutral', 'negative', 'mixed')"
    ))
    op.execute(sa.text(
        "CREATE TYPE draft_status AS ENUM "
        "('pending_review', 'approved', 'rejected', 'copied', 'superseded')"
    ))
    op.execute(sa.text(
        "CREATE TYPE job_type AS ENUM "
        "('full_sync', 'incremental_sync', 'profile_rebuild', 'triage', 'draft_generate')"
    ))
    op.execute(sa.text(
        "CREATE TYPE job_status AS ENUM "
        "('queued', 'running', 'completed', 'failed', 'cancelled', 'retrying')"
    ))

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_active", "users", ["is_active"],
                    postgresql_where=sa.text("is_active = true"))

    # ── platform_connections ──────────────────────────────────────────────────
    op.create_table(
        "platform_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.Enum(name="platform_type", create_type=False), nullable=False),
        sa.Column("platform_account_id", sa.String(), nullable=False),
        sa.Column("platform_email", sa.String(), nullable=True),
        sa.Column("encrypted_access_token", postgresql.BYTEA(), nullable=False),
        sa.Column("encrypted_refresh_token", postgresql.BYTEA(), nullable=True),
        sa.Column("token_iv", postgresql.BYTEA(), nullable=False),
        sa.Column("token_tag", postgresql.BYTEA(), nullable=False),
        sa.Column("token_key_id", sa.String(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_scopes", postgresql.ARRAY(sa.String()), nullable=False,
                  server_default="{}"),
        sa.Column("status", sa.Enum(name="connection_status", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("last_history_id", sa.String(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("sync_cursor", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "platform", "platform_account_id",
                            name="uq_platform_connections_user_platform_account"),
    )
    op.create_index("ix_platform_connections_user_id", "platform_connections", ["user_id"])
    op.create_index("ix_platform_connections_status", "platform_connections", ["status"])
    op.create_index(
        "ix_platform_connections_expires", "platform_connections", ["token_expires_at"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # ── threads ───────────────────────────────────────────────────────────────
    op.create_table(
        "threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("platform_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.Enum(name="platform_type", create_type=False), nullable=False),
        sa.Column("platform_thread_id", sa.String(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("participants", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("labels", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("first_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_unread", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_in_inbox", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("connection_id", "platform_thread_id",
                            name="uq_threads_connection_platform_thread"),
    )
    op.create_index("ix_threads_user_id", "threads", ["user_id"])
    op.create_index("ix_threads_connection_id", "threads", ["connection_id"])
    op.create_index(
        "ix_threads_user_last_msg", "threads", ["user_id", sa.text("last_message_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_threads_inbox", "threads", ["user_id", "is_in_inbox"],
        postgresql_where=sa.text("is_in_inbox = true AND deleted_at IS NULL"),
    )

    # ── messages ──────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("platform_connections.id"), nullable=False),
        sa.Column("platform_message_id", sa.String(), nullable=False),
        sa.Column("from_email", sa.String(), nullable=False),
        sa.Column("from_name", sa.String(), nullable=True),
        sa.Column("to_emails", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("cc_emails", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("reply_to_email", sa.String(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body_plain", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("internal_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("folder", sa.Enum(name="message_folder", create_type=False),
                  nullable=False, server_default="inbox"),
        sa.Column("labels", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("attachment_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("headers", postgresql.JSONB(), nullable=True),
        sa.Column("is_sent_by_user", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("connection_id", "platform_message_id",
                            name="uq_messages_connection_platform_message"),
    )
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"])
    op.create_index("ix_messages_user_id", "messages", ["user_id"])
    op.create_index(
        "ix_messages_sent_by_user", "messages", ["user_id", sa.text("internal_date DESC")],
        postgresql_where=sa.text("is_sent_by_user = true AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_messages_body_fts", "messages",
        [sa.text("to_tsvector('english', coalesce(body_plain, ''))")],
        postgresql_using="gin",
    )

    # ── thread_analyses ───────────────────────────────────────────────────────
    op.create_table(
        "thread_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority", sa.Enum(name="priority_level", create_type=False), nullable=False),
        sa.Column("priority_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("action_items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("requires_reply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sentiment", sa.Enum(name="sentiment_type", create_type=False), nullable=True),
        sa.Column("source_message_ids", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("source_message_hash", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("prompt_template_hash", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("raw_llm_response", postgresql.JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_analyses_thread_id", "thread_analyses", ["thread_id"])
    op.create_index("ix_analyses_user_id", "thread_analyses", ["user_id"])
    op.create_index(
        "ix_analyses_user_priority", "thread_analyses", ["user_id", "priority"],
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "ix_analyses_current", "thread_analyses", ["thread_id"],
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "ix_analyses_requires_reply", "thread_analyses", ["user_id", "requires_reply"],
        postgresql_where=sa.text("is_current = true AND requires_reply = true"),
    )

    # ── drafts ────────────────────────────────────────────────────────────────
    op.create_table(
        "drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("thread_analyses.id"), nullable=True),
        sa.Column("subject_line", sa.Text(), nullable=True),
        sa.Column("body_plain", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("tone_used", sa.String(), nullable=True),
        sa.Column("status", sa.Enum(name="draft_status", create_type=False),
                  nullable=False, server_default="pending_review"),
        sa.Column("user_edited_body", sa.Text(), nullable=True),
        sa.Column("feedback_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("regeneration_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_draft_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("drafts.id"), nullable=True),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("prompt_template_hash", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("raw_llm_response", postgresql.JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_drafts_thread_id", "drafts", ["thread_id"])
    op.create_index("ix_drafts_user_id", "drafts", ["user_id"])
    op.create_index(
        "ix_drafts_pending", "drafts", ["user_id", "status"],
        postgresql_where=sa.text("status = 'pending_review'"),
    )

    # ── user_profiles ─────────────────────────────────────────────────────────
    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("platform_connections.id"), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("voice_summary", sa.Text(), nullable=True),
        sa.Column("tone_attributes", postgresql.ARRAY(sa.String()), nullable=False,
                  server_default="{}"),
        sa.Column("avg_response_latency_hours", sa.Numeric(6, 2), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("messages_analyzed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("analyzed_date_range_start", sa.Date(), nullable=True),
        sa.Column("analyzed_date_range_end", sa.Date(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("prompt_template_hash", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])
    op.create_index(
        "ix_user_profiles_current", "user_profiles", ["user_id", "connection_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    # ── sync_jobs ─────────────────────────────────────────────────────────────
    op.create_table(
        "sync_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("platform_connections.id"), nullable=True),
        sa.Column("job_type", sa.Enum(name="job_type", create_type=False), nullable=False),
        sa.Column("status", sa.Enum(name="job_status", create_type=False),
                  nullable=False, server_default="queued"),
        sa.Column("queue_job_id", sa.String(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("messages_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_total", sa.Integer(), nullable=True),
        sa.Column("quota_units_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_detail", postgresql.JSONB(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("job_metadata", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_sync_jobs_user_id", "sync_jobs", ["user_id"])
    op.create_index("ix_sync_jobs_connection_id", "sync_jobs", ["connection_id"])
    op.create_index(
        "ix_sync_jobs_active", "sync_jobs", ["status"],
        postgresql_where=sa.text("status IN ('queued', 'running', 'retrying')"),
    )


def downgrade() -> None:
    op.drop_table("sync_jobs")
    op.drop_table("user_profiles")
    op.drop_table("drafts")
    op.drop_table("thread_analyses")
    op.drop_table("messages")
    op.drop_table("threads")
    op.drop_table("platform_connections")
    op.drop_table("users")

    op.execute(sa.text("DROP TYPE IF EXISTS job_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS job_type"))
    op.execute(sa.text("DROP TYPE IF EXISTS draft_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS sentiment_type"))
    op.execute(sa.text("DROP TYPE IF EXISTS priority_level"))
    op.execute(sa.text("DROP TYPE IF EXISTS message_folder"))
    op.execute(sa.text("DROP TYPE IF EXISTS connection_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS platform_type"))
