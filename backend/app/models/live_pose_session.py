"""Separate successful scene-analysis ledger; never touches image credits."""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, UniqueConstraint, Index
from app.database.base import Base

class LivePoseSession(Base):
    __tablename__ = "LivePoseSession"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_live_pose_request"),
                     Index("ix_live_pose_usage", "user_id", "created_at"))
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("User.id"), nullable=False)
    request_key = Column(String(36), nullable=False)
    scene_hash = Column(String(64), nullable=False)
    plan_code = Column(String(16), nullable=False)
    created_at = Column(DateTime, nullable=False)
    result = Column(JSON, nullable=False)
