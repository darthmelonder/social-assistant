import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import DraftStatus


class Draft(Base, TimestampMixin):
    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = uuid_pk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("thread_analyses.id"), nullable=True
    )

    subject_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_plain: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_used: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DraftStatus.PENDING_REVIEW,
    )
    user_edited_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    regeneration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drafts.id"), nullable=True
    )

    # AI model provenance
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    prompt_template_hash: Mapped[str] = mapped_column(String, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_llm_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    thread: Mapped["Thread"] = relationship(back_populates="drafts")  # noqa: F821
    analysis: Mapped["ThreadAnalysis | None"] = relationship(back_populates="drafts")  # noqa: F821
    parent_draft: Mapped["Draft | None"] = relationship(remote_side="Draft.id")
