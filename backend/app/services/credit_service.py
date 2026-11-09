"""Shared current-period credit accounting; callers serialize using the User lock."""
import calendar
from datetime import datetime
from hashlib import sha256
from sqlalchemy import select
from fastapi import HTTPException
from app.models.subscription_plan import SubscriptionPlan
from app.models.credit_transaction import CreditTransaction


def anniversary(anchor, offset):
    month = anchor.year * 12 + anchor.month - 1 + offset
    year, zero_month = divmod(month, 12)
    return anchor.replace(year=year, month=zero_month + 1,
                          day=min(anchor.day, calendar.monthrange(year, zero_month + 1)[1]))


def period(subscription, now):
    if subscription.plan_kind == "trial":
        return subscription.start_date, subscription.end_date
    anchor = subscription.start_date
    offset = (now.year - anchor.year) * 12 + now.month - anchor.month
    if anniversary(anchor, offset) > now:
        offset -= 1
    return anniversary(anchor, offset), anniversary(anchor, offset + 1)


def balance(db, subscription, now, grant=False):
    start, end = period(subscription, now)
    rows = list(db.scalars(select(CreditTransaction).where(
        CreditTransaction.user_id == subscription.user_id,
        CreditTransaction.subscription_id == subscription.id,
        CreditTransaction.period_start == start,
        CreditTransaction.period_end == end,
    ).execution_options(populate_existing=True).with_for_update()))
    plan = db.get(SubscriptionPlan, subscription.plan_id)
    if (plan is None or plan.code != subscription.plan_kind or plan.user_role != "owner"
            or not plan.is_active or plan.monthly_credits < 0):
        raise HTTPException(503, "Subscription credits are unavailable.")
    allowance = plan.monthly_credits
    granted = any(row.transaction_type == "grant" for row in rows)
    if not granted and grant:
        key = sha256(f"grant:{subscription.id}:{start.isoformat()}".encode()).digest()
        db.add(CreditTransaction(user_id=subscription.user_id, subscription_id=subscription.id,
            credits_change=allowance, transaction_type="grant", created_at=now,
            period_start=start, period_end=end, operation_key=key, request_hash=key))
        db.flush()
    # A read can describe the current allowance without inserting a ledger row.
    remaining = sum(row.credits_change for row in rows) + (0 if granted else allowance)
    if remaining < 0:
        raise HTTPException(503, "Credit ledger requires review.")
    return remaining, start, end
