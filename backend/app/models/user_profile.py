import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_connections.id"), nullable=False
    )

    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    voice_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_attributes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    avg_response_latency_hours: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Full structured output from profile-building LLM call:
    # { vocabulary_sample, topic_clusters, greeting_patterns,
    #   sign_off_patterns, avg_email_length_words, formality_score,
    #   relationship_contexts }
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    messages_analyzed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analyzed_date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    analyzed_date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # AI model provenance
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    prompt_template_hash: Mapped[str] = mapped_column(String, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="user_profiles")  # noqa: F821
    connection: Mapped["PlatformConnection"] = relationship(back_populates="user_profiles")  # noqa: F821
