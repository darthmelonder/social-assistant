import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import ConnectionStatus, PlatformType


class PlatformConnection(Base, TimestampMixin):
    __tablename__ = "platform_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", "platform_account_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[PlatformType] = mapped_column(
        Enum(PlatformType, name="platform_type"), nullable=False
    )
    platform_account_id: Mapped[str] = mapped_column(String, nullable=False)
    platform_email: Mapped[str | None] = mapped_column(String, nullable=True)

    # AES-256-GCM encrypted token fields — never store plaintext
    encrypted_access_token: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    encrypted_refresh_token: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    token_iv: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    token_tag: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    token_key_id: Mapped[str] = mapped_column(String, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granted_scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Sync state
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status"),
        nullable=False,
        default=ConnectionStatus.PENDING,
    )
    last_history_id: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="platform_connections")  # noqa: F821
    threads: Mapped[list["Thread"]] = relationship(back_populates="connection", cascade="all, delete-orphan")  # noqa: F821
    user_profiles: Mapped[list["UserProfile"]] = relationship(back_populates="connection", cascade="all, delete-orphan")  # noqa: F821
    sync_jobs: Mapped[list["SyncJob"]] = relationship(back_populates="connection")  # noqa: F821
