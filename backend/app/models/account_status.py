from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, String, UniqueConstraint, Index
from app.database.base import Base

class AccountStatus(Base):
    __tablename__='AccountStatus'
    user_id=Column(Integer,ForeignKey('User.id'),primary_key=True)
    is_active=Column(Boolean,nullable=False,default=True)
    version=Column(Integer,nullable=False,default=0)
    changed_at=Column(DateTime,nullable=False)

class AccountStatusAudit(Base):
    __tablename__='AccountStatusAudit'
    __table_args__=(UniqueConstraint('user_id','version',name='uq_account_status_audit_version'),Index('ix_account_status_audit_user_time','user_id','changed_at'))
    id=Column(Integer,primary_key=True)
    user_id=Column(Integer,ForeignKey('User.id'),nullable=False)
    actor_id=Column(Integer,ForeignKey('User.id'),nullable=False)
    old_active=Column(Boolean,nullable=False)
    new_active=Column(Boolean,nullable=False)
    version=Column(Integer,nullable=False)
    changed_at=Column(DateTime,nullable=False)
