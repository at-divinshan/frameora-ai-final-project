"""Credit ledger mapping. Existing generation FK is managed by migration DDL."""
from sqlalchemy import Column, Computed, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BINARY, VARBINARY
from app.database.base import Base

class CreditTransaction(Base):
    __tablename__ = "CreditTransaction"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "subscription_id"], ["Subscription.user_id", "Subscription.id"], name="m003_fk_credit_subscription_owner"),
        UniqueConstraint("user_id", "operation_key", name="m003_uq_credit_operation"),
        UniqueConstraint("user_id", "subscription_id", "grant_period_start", name="m003_uq_credit_grant"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("User.id"), nullable=False)
    generation_id = Column(Integer, ForeignKey("AIGeneration.id", name="fk_credit_generation"))
    credits_change = Column(Integer, nullable=False)
    transaction_type = Column(String(30), nullable=False)
    created_at = Column(DateTime, nullable=False)
    subscription_id = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    operation_key = Column(VARBINARY(128), nullable=False)
    request_hash = Column(BINARY(32), nullable=False)
    grant_period_start = Column(DateTime, Computed("CASE WHEN transaction_type = 'grant' THEN period_start ELSE NULL END", persisted=True))
