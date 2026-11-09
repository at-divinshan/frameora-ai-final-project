"""Mapping for the existing CustomerProject columns only."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CustomerProject(Base):
    __tablename__ = "CustomerProject"
    __table_args__ = (
        Index(
            "m003_ix_project_owner_live_order",
            "studio_owner_id",
            "deleted_at",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    studio_owner_id: Mapped[int] = mapped_column(ForeignKey("User.id"), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    project_title: Mapped[str | None] = mapped_column(String(150))
    customer_contact: Mapped[str | None] = mapped_column(String(100))
    event_type: Mapped[str | None] = mapped_column(String(100))
    shoot_location: Mapped[str | None] = mapped_column(String(255))
    shooting_date: Mapped[date | None] = mapped_column(Date)
    requirements: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)