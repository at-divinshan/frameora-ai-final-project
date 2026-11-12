"""Read-only, allowlisted account billing details. Never grants or renews credits."""
from sqlalchemy import select, func, inspect
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.credit_transaction import CreditTransaction
from app.models.free_generation_allowance import FreeGenerationAllowance
from app.models.payment import Payment
from app.services import credit_service, subscription_service, free_generation_service


def available(db, *models):
    inspector = inspect(db.connection())
    return all(inspector.has_table(m.__tablename__) and
               set(m.__table__.columns.keys()) <= {c['name'] for c in inspector.get_columns(m.__tablename__)}
               for m in models)


def subscription_details(db, user):
    result = dict(plan=None, status=None, start_date=None, end_date=None,
                  allocated=None, used=None, remaining=None, period_start=None,
                  period_end=None, allowance_status=None, note=None)
    if user.role == 'user':
        result['note'] = 'Monthly credits are not active. This account uses a one-time four-image generation allowance, not a credit balance.'
        if available(db, FreeGenerationAllowance):
            # Shared read-only status semantics: no allowance row means available.
            result['allowance_status'] = free_generation_service._status_for(db, user.id)
        return result
    if not available(db, Subscription, SubscriptionPlan):
        result['note'] = 'Subscription records are not available.'
        return result
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id)
                    .order_by((Subscription.status == 'active').desc(), Subscription.start_date.desc(), Subscription.id.desc()).limit(1))
    if sub is None:
        result['note'] = 'No recorded subscription.'
        return result
    plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id,
                                                   SubscriptionPlan.user_role == user.role))
    now = subscription_service.clock()
    expired = sub.end_date is not None and sub.end_date <= now
    result.update(plan=plan.name if plan else None, status='expired' if sub.status == 'active' and expired else sub.status,
                  start_date=sub.start_date, end_date=sub.end_date)
    if sub.status != 'active' or expired or sub.start_date > now:
        result['note'] = 'Last recorded subscription. No current credit allocation is shown.'
        return result
    if sub.plan_kind not in ('basic', 'trial', 'pro') or not available(db, CreditTransaction):
        result['note'] = 'Credit ledger is not available.'
        return result
    if sub.plan_kind == 'trial' and sub.end_date is None:
        result['note'] = 'Credit period is not available.'
        return result
    start, end = credit_service.period(sub, now)
    rows = list(db.scalars(select(CreditTransaction).where(
        CreditTransaction.user_id == user.id, CreditTransaction.subscription_id == sub.id,
        CreditTransaction.period_start == start, CreditTransaction.period_end == end)))
    if not rows or not any(r.transaction_type == 'grant' for r in rows):
        result['note'] = 'No recorded allocation for the current period. Pending grants and renewals are not counted.'
        return result
    if any(r.transaction_type not in ('grant','spend','refund') or
           (r.transaction_type == 'spend' and r.credits_change > 0) or
           (r.transaction_type != 'spend' and r.credits_change < 0) for r in rows):
        result['note'] = 'Credit ledger requires review.'
        return result
    allocated = sum(r.credits_change for r in rows if r.transaction_type == 'grant')
    remaining = sum(r.credits_change for r in rows)
    if not 0 <= remaining <= allocated:
        result['note'] = 'Credit ledger requires review.'
        return result
    result.update(allocated=allocated, used=allocated-remaining, remaining=remaining,
                  period_start=start, period_end=end,
                  note='Recorded current-period credits. Used credits are net deductions after refunds and include in-progress reservations.')
    return result


def payment_details(db, user, page):
    result = dict(available=False, items=[], total=None, page=page, page_size=20)
    if not available(db, Payment):
        return result
    total = db.scalar(select(func.count()).select_from(Payment).where(Payment.user_id == user.id))
    rows = list(db.scalars(select(Payment).where(Payment.user_id == user.id)
                .order_by(Payment.created_at.desc(), Payment.id.desc()).offset((page-1)*20).limit(20)))
    names = {}
    if rows and available(db, Subscription, SubscriptionPlan):
        names = dict(db.execute(select(Subscription.id, SubscriptionPlan.name)
            .join(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id)
            .where(Subscription.user_id == user.id, SubscriptionPlan.user_role == user.role,
                   Subscription.id.in_([r.subscription_id for r in rows]))).all())
    result.update(available=True, total=total, items=[dict(
        record_id=r.id, transaction_id=None, date=r.created_at,
        amount=str(r.amount) if r.amount is not None else None, currency=None,
        method=None, plan=names.get(r.subscription_id), status=r.status) for r in rows])
    return result
