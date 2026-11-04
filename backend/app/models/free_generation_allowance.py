"""Mapping for the proposed per-account free-generation allowance table."""

from datetime import datetime

from sqlalchemy import (
    BINARY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FreeGenerationAllowance(Base):
    __tablename__ = "FreeGenerationAllowance"
    __table_args__ = (
        Index(
            "m005_ix_free_generation_state_reserved",
            "state",
            "reserved_at",
        ),
        CheckConstraint(
            "(state = 'available' AND reservation_key IS NULL AND generation_id IS NULL "
            "AND reserved_at IS NULL AND consumed_at IS NULL) OR "
            "(state = 'reserved' AND reservation_key IS NOT NULL AND generation_id IS NOT NULL "
            "AND reserved_at IS NOT NULL AND consumed_at IS NULL) OR "
            "(state = 'consumed' AND reservation_key IS NULL AND generation_id IS NOT NULL "
            "AND reserved_at IS NOT NULL AND consumed_at IS NOT NULL)",
            name="m005_ck_free_generation_state",
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("User.id"), primary_key=True)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'available'")
    )
    reservation_key: Mapped[bytes | None] = mapped_column(BINARY(32))
    generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("AIGeneration.id"), unique=True
    )
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
