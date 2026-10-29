"""Mapping of the existing, case-sensitive MySQL User table. No DDL is run."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, text
from sqlalchemy.dialects.mysql import VARBINARY, BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class User(Base):
    __tablename__ = "User"
    __table_args__ = (Index("uq_user_google_sub", "google_sub", unique=True),)
    # Legacy databases lack auth_version. Never implicitly fetch server defaults.
    __mapper_args__ = {"eager_defaults": False}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    profile_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    privacy_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    google_sub: Mapped[bytes | None] = mapped_column(VARBINARY(255), nullable=True)
    auth_version: Mapped[int] = mapped_column(
        BigInteger().with_variant(BIGINT(unsigned=True), "mysql"),
        nullable=False, server_default=text("0"), deferred=True,
    )
