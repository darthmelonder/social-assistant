import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import MessageFolder


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("connection_id", "platform_message_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_connections.id"), nullable=False
    )
    platform_message_id: Mapped[str] = mapped_column(String, nullable=False)

    from_email: Mapped[str] = mapped_column(String, nullable=False)
    from_name: Mapped[str | None] = mapped_column(String, nullable=True)
    to_emails: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    cc_emails: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    reply_to_email: Mapped[str | None] = mapped_column(String, nullable=True)

    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_plain: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    internal_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    folder: Mapped[MessageFolder] = mapped_column(
        Enum(MessageFolder, name="message_folder", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MessageFolder.INBOX,
    )
    labels: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # [{ filename, mimeType, size_bytes, attachment_id }]
    attachment_metadata: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_sent_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped["Thread"] = relationship(back_populates="messages")  # noqa: F821
