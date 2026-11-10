from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
from app.database.base import Base

class ImageFeedback(Base):
    __tablename__ = "ImageFeedback"
    __table_args__ = (UniqueConstraint("author_id", "request_key", name="uq_feedback_request"),
                     Index("ix_feedback_project_image", "project_id", "asset_id", "id"))
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("CustomerProject.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("MediaAsset.id"), nullable=False)
    share_link_id = Column(Integer, ForeignKey("ShareLink.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("User.id"), nullable=False)
    request_key = Column(String(36), nullable=False)
    comment = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    revised_asset_id = Column(Integer, ForeignKey("MediaAsset.id"))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
