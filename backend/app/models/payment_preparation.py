"""Proposed v4 mappings only. Importing this module never creates schema."""
from sqlalchemy import (Column, Integer, String, Boolean, DateTime, ForeignKey,
    ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index, BigInteger)
from sqlalchemy.dialects.mysql import BINARY
from app.database.base import Base

class PaymentCheckout(Base):
    __tablename__ = 'PaymentCheckout'
    __table_args__ = (
        UniqueConstraint('user_id','request_key',name='uq_checkout_request'),
        UniqueConstraint('provider_session_id',name='uq_checkout_session'),
        UniqueConstraint('provider_payment_id',name='uq_checkout_payment_intent'),
        UniqueConstraint('payment_id',name='uq_checkout_record'),
        UniqueConstraint('user_id','id',name='uq_checkout_owner'),
        CheckConstraint('amount_minor > 0 AND credits > 0',name='ck_checkout_amount'),
        CheckConstraint('livemode = 0',name='ck_checkout_test_only'),
        CheckConstraint("state IN ('pending','open','fulfilled','revoked','review')",name='ck_checkout_state'),
        Index('ix_checkout_owner_state','user_id','state'), {'mysql_engine':'InnoDB'},
    )
    id = Column(Integer,primary_key=True)
    user_id = Column(Integer,ForeignKey('User.id'),nullable=False)
    plan_id = Column(Integer,ForeignKey('SubscriptionPlan.id'),nullable=False)
    plan_code = Column(String(16),nullable=False)
    request_key = Column(BINARY(32),nullable=False)
    request_hash = Column(BINARY(32),nullable=False)
    amount_minor = Column(BigInteger,nullable=False)
    currency = Column(String(3),nullable=False)
    credits = Column(Integer,nullable=False)
    state = Column(String(16),nullable=False)
    livemode = Column(Boolean,nullable=False,default=False)
    provider_session_id = Column(String(255))
    provider_payment_id = Column(String(255))
    payment_id = Column(Integer,ForeignKey('Payment.id'))
    created_at = Column(DateTime,nullable=False)
    expires_at = Column(DateTime,nullable=False)
    verified_at = Column(DateTime)
    revoked_at = Column(DateTime)

class PaymentWebhookEvent(Base):
    __tablename__ = 'PaymentWebhookEvent'
    __table_args__ = (UniqueConstraint('event_id',name='uq_payment_event'),
        CheckConstraint('livemode = 0',name='ck_payment_event_test_only'),
        Index('ix_payment_event_checkout','checkout_id'), {'mysql_engine':'InnoDB'})
    id = Column(Integer,primary_key=True)
    event_id = Column(String(255),nullable=False)
    event_type = Column(String(100),nullable=False)
    payload_hash = Column(BINARY(32),nullable=False)
    livemode = Column(Boolean,nullable=False,default=False)
    checkout_id = Column(Integer,ForeignKey('PaymentCheckout.id'),nullable=False)
    received_at = Column(DateTime,nullable=False)
    processed_at = Column(DateTime,nullable=False)
    outcome = Column(String(30),nullable=False)
    provider_object_id = Column(String(255),nullable=False)
    amount_minor = Column(BigInteger)
    currency = Column(String(3),nullable=False)

class PaidCreditAllocation(Base):
    __tablename__ = 'PaidCreditAllocation'
    __table_args__ = (
        ForeignKeyConstraint(['user_id','checkout_id'],['PaymentCheckout.user_id','PaymentCheckout.id'],name='fk_allocation_checkout_owner'),
        ForeignKeyConstraint(['user_id','subscription_id'],['Subscription.user_id','Subscription.id'],name='fk_allocation_subscription_owner'),
        UniqueConstraint('checkout_id',name='uq_allocation_checkout'),
        UniqueConstraint('subscription_id',name='uq_allocation_subscription'),
        UniqueConstraint('grant_transaction_id',name='uq_allocation_grant'),
        CheckConstraint('period_end > period_start AND credits > 0',name='ck_allocation_period'),
        {'mysql_engine':'InnoDB'},
    )
    id = Column(Integer,primary_key=True)
    user_id = Column(Integer,ForeignKey('User.id'),nullable=False)
    checkout_id = Column(Integer,nullable=False)
    subscription_id = Column(Integer,nullable=False)
    grant_transaction_id = Column(Integer,ForeignKey('CreditTransaction.id'),nullable=False)
    credits = Column(Integer,nullable=False)
    period_start = Column(DateTime,nullable=False)
    period_end = Column(DateTime,nullable=False)
    created_at = Column(DateTime,nullable=False)
    revoked_at = Column(DateTime)
