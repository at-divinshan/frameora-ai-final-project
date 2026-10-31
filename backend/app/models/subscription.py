"""Migration 003 history mapping; migrations remain the authoritative DDL."""
from sqlalchemy import Column, Computed, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import VARBINARY
from app.database.base import Base

class Subscription(Base):
    __tablename__ = "Subscription"
    __table_args__ = (
        UniqueConstraint("trial_owner_id", name="m003_uq_trial_owner"),
        UniqueConstraint("active_owner_id", name="m003_uq_active_owner"),
        UniqueConstraint("pending_owner_id", name="m003_uq_pending_owner"),
        UniqueConstraint("user_id", "activation_key", name="m003_uq_activation"),
        UniqueConstraint("user_id", "id", name="m003_uq_sub_user_id"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("User.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("SubscriptionPlan.id"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    status = Column(String(30), nullable=False)
    plan_kind = Column(String(16), nullable=False)
    activation_key = Column(VARBINARY(64), nullable=False)
    trial_owner_id = Column(Integer, Computed("CASE WHEN plan_kind = 'trial' THEN user_id ELSE NULL END", persisted=True))
    active_owner_id = Column(Integer, Computed("CASE WHEN status = 'active' THEN user_id ELSE NULL END", persisted=True))
    pending_owner_id = Column(Integer, Computed("CASE WHEN status = 'pending_payment' THEN user_id ELSE NULL END", persisted=True))
