import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk
from app.models.enums import PriorityLevel, SentimentType


class ThreadAnalysis(Base):
    __tablename__ = "thread_analyses"

    id: Mapped[uuid.UUID] = uuid_pk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    priority: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel, name="priority_level"), nullable=False
    )
    priority_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # [{ description, due_date_hint, assignee_hint, completed }]
    action_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    requires_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sentiment: Mapped[SentimentType | None] = mapped_column(
        Enum(SentimentType, name="sentiment_type"), nullable=True
    )

    # Snapshot of what was analyzed — used to detect when re-triage is needed
    source_message_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    source_message_hash: Mapped[str] = mapped_column(String, nullable=False)

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    thread: Mapped["Thread"] = relationship(back_populates="analyses")  # noqa: F821
    drafts: Mapped[list["Draft"]] = relationship(back_populates="analysis")  # noqa: F821
