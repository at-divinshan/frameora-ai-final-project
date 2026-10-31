"""Catalogue mapping for migration 003. Importing this module never runs DDL."""
from sqlalchemy import Boolean, CHAR, Column, Integer, Numeric, String, UniqueConstraint
from app.database.base import Base

class SubscriptionPlan(Base):
    __tablename__ = "SubscriptionPlan"
    __table_args__ = (UniqueConstraint("user_role", "code", name="m003_uq_plan_role_code"),)
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    user_role = Column(String(30), nullable=False)
    monthly_credits = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, nullable=False)
    max_projects = Column(Integer)
    max_share_links = Column(Integer)
    trial_days = Column(Integer)
    currency = Column(CHAR(3), nullable=False)
    code = Column(String(16))
