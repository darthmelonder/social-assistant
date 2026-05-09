import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import PlatformType


class Thread(Base, TimestampMixin):
    __tablename__ = "threads"
    __table_args__ = (
        UniqueConstraint("connection_id", "platform_thread_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[PlatformType] = mapped_column(
        Enum(PlatformType, name="platform_type", create_type=False), nullable=False
    )
    platform_thread_id: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{ email, name, role: "sender"|"recipient"|"cc"|"bcc" }]
    participants: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    labels: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    first_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_unread: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_in_inbox: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="threads")  # noqa: F821
    connection: Mapped["PlatformConnection"] = relationship(back_populates="threads")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(back_populates="thread", cascade="all, delete-orphan")  # noqa: F821
    analyses: Mapped[list["ThreadAnalysis"]] = relationship(back_populates="thread", cascade="all, delete-orphan")  # noqa: F821
    drafts: Mapped[list["Draft"]] = relationship(back_populates="thread", cascade="all, delete-orphan")  # noqa: F821
