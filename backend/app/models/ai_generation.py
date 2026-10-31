"""SQLAlchemy mapping for the existing AIGeneration table."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AIGeneration(Base):
    __tablename__ = "AIGeneration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_id: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100))
    quality: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    guidance_text: Mapped[str | None] = mapped_column(Text().with_variant(LONGTEXT(), 'mysql'))
    is_favorite: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("0")
    )
