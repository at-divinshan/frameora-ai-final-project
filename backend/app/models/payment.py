"""Read mapping of existing payment records; no gateway or schema changes."""
from sqlalchemy import Column, Integer, Numeric, String, DateTime, ForeignKey
from app.database.base import Base

class Payment(Base):
    __tablename__ = 'Payment'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('User.id'))
    subscription_id = Column(Integer, ForeignKey('Subscription.id'))
    amount = Column(Numeric(10, 2))
    status = Column(String(30))
    created_at = Column(DateTime)
