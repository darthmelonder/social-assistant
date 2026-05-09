import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    platform_connections: Mapped[list["PlatformConnection"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    threads: Mapped[list["Thread"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
    user_profiles: Mapped[list["UserProfile"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
    sync_jobs: Mapped[list["SyncJob"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
