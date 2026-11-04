"""Mapping of the existing MediaAsset table; no schema creation is performed."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MediaAsset(Base):
    __tablename__ = "MediaAsset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Existing foreign keys remain database-managed, as in AIGeneration.
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_id: Mapped[int | None] = mapped_column(Integer)
    generation_id: Mapped[int | None] = mapped_column(Integer)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Generation storage should put an opaque private key here, never a public URL.
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
