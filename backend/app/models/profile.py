"""Mapping of the existing UserProfile table; declaring it never runs DDL."""

from datetime import datetime

from sqlalchemy import DateTime, FetchedValue, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserProfile(Base):
    __tablename__ = "UserProfile"
    __mapper_args__ = {"eager_defaults": False}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("User.id"), nullable=False, unique=True)
    # Deferred and omitted on INSERT until separate migration 004 is applied.
    studio_photo: Mapped[str | None] = mapped_column(String(68), deferred=True, server_default=FetchedValue())
    studio_name: Mapped[str | None] = mapped_column(String(150))
    studio_phone: Mapped[str | None] = mapped_column(String(20))
    studio_address: Mapped[str | None] = mapped_column(String(255))
    studio_city: Mapped[str | None] = mapped_column(String(100))
    studio_description: Mapped[str | None] = mapped_column(Text)
    onboarding_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'pending_studio'")
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime)
