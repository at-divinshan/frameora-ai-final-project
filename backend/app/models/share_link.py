from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ShareLink(Base):
    __tablename__ = "ShareLink"
    __table_args__ = (
        Index(
            "m003_ix_share_generation_active",
            "generation_id",
            "is_active",
            "expires_at",
            "created_at",
            "id",
        ),
        Index(
            "m003_ix_share_generation_order",
            "generation_id",
            "is_active",
            "created_at",
            "id",
        ),
        Index("token_hash", "token_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("CustomerProject.id", name="fk_share_project"), nullable=True
    )
    generation_id: Mapped[int] = mapped_column(
        ForeignKey("AIGeneration.id", name="fk_share_generation"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )