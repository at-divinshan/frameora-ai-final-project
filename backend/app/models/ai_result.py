"""Mapping of the existing AIResult table, verified against MySQL metadata."""

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AIResult(Base):
    __tablename__ = "AIResult"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Existing foreign keys remain database-managed, as in AIGeneration.
    generation_id: Mapped[int] = mapped_column(Integer, nullable=False)
