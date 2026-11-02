"""SQLAlchemy mapping for the existing PhotographyPlan table."""

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class PhotographyPlan(Base):
    __tablename__ = "PhotographyPlan"
    __table_args__ = (
        CheckConstraint("people_count BETWEEN 1 AND 10", name="ck_photography_plan_people_count"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("User.id"), nullable=False)
    # CustomerProject is not mapped by this application yet. Its existing MySQL
    # foreign key remains database-managed; an unresolved ORM FK breaks even NULL inserts.
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photography_type: Mapped[str] = mapped_column(String(50), nullable=False)
    people_count: Mapped[int] = mapped_column(Integer, nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shoot_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    preferences: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    user: Mapped["User"] = relationship(back_populates="photography_plans")