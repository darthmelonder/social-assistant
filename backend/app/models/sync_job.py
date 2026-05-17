import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk
from app.models.enums import JobStatus, JobType


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("platform_connections.id"), nullable=True, index=True
    )

    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=JobStatus.QUEUED,
    )

    queue_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Crash-resumable cursor — pageToken saved after each page batch
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    messages_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_units_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    triggered_by: Mapped[str | None] = mapped_column(String, nullable=True)
    job_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="sync_jobs")  # noqa: F821
    connection: Mapped["PlatformConnection | None"] = relationship(back_populates="sync_jobs")  # noqa: F821
