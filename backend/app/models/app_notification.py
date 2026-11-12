from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint, Index
from app.database.base import Base

class AppNotification(Base):
    __tablename__ = 'AppNotification'
    __table_args__ = (UniqueConstraint('user_id', 'event_key', name='uq_app_notification_event'),
                     Index('ix_app_notification_unread', 'user_id', 'is_read', 'id'))
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('User.id'), nullable=False)
    event_key = Column(String(190), nullable=False)
    message = Column(String(500), nullable=False)
    href = Column(String(200), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False)
