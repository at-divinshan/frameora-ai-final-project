"""Never infer paid credits from plan catalogue values or unpaid anniversaries."""
from fastapi import HTTPException
from decimal import Decimal
from sqlalchemy import select
from app.core.stripe_test import require_release
from app.models.payment_preparation import PaymentCheckout, PaidCreditAllocation
from app.models.credit_transaction import CreditTransaction
from app.models.payment import Payment
from app.models.user import User
from app.models.subscription_plan import SubscriptionPlan
from app.core.stripe_prices import paid_plan

def proof(db, sub, now, *, settlement=False):
    require_release()  # Also blocks display/spending on the pre-v4 deployment.
    from app.services.payment_schema import require_payment_schema
    require_payment_schema(db)
    row = db.execute(select(PaidCreditAllocation,PaymentCheckout,Payment,CreditTransaction)
        .select_from(PaidCreditAllocation)
        .join(PaymentCheckout,PaymentCheckout.id == PaidCreditAllocation.checkout_id)
        .join(Payment,Payment.id == PaymentCheckout.payment_id)
        .join(CreditTransaction,CreditTransaction.id == PaidCreditAllocation.grant_transaction_id)
        .where(PaidCreditAllocation.subscription_id == sub.id,
               PaidCreditAllocation.user_id == sub.user_id).with_for_update()).one_or_none()
    if row is None: raise HTTPException(503,'Verified paid allocation is unavailable.')
    allocation, checkout, payment, grant = row
    user=db.get(User,sub.user_id)
    plan=db.get(SubscriptionPlan,sub.plan_id)
    if user is None or plan is None or user.role!=plan.user_role:
        raise HTTPException(503,'Paid account role does not match the purchased plan.')
    approved=paid_plan(plan.user_role,sub.plan_kind)
    if checkout.amount_minor!=approved.amount_minor or checkout.credits!=approved.credits:
        raise HTTPException(503,'Paid allocation differs from the approved plan.')
    if ((not settlement and (sub.status != 'active' or sub.end_date is None or not sub.start_date <= now < sub.end_date))
            or sub.status == 'cancelled'
            or checkout.state != 'fulfilled' or checkout.livemode is not False or not checkout.verified_at
            or checkout.currency != approved.currency
            or checkout.revoked_at or allocation.revoked_at or payment.status != 'succeeded'
            or checkout.user_id != sub.user_id or payment.user_id != sub.user_id
            or checkout.plan_id != sub.plan_id or checkout.plan_code != sub.plan_kind
            or payment.subscription_id != sub.id or not checkout.provider_payment_id
            or payment.amount != Decimal(checkout.amount_minor)/100
            or allocation.period_start != sub.start_date or allocation.period_end != sub.end_date
            or allocation.credits != checkout.credits or grant.credits_change != allocation.credits
            or grant.transaction_type != 'grant' or grant.user_id != sub.user_id
            or grant.subscription_id != sub.id or grant.period_start != sub.start_date
            or grant.period_end != sub.end_date):
        raise HTTPException(503,'Verified paid allocation is unavailable.')
    return allocation

def balance(db, sub, now):
    allocation = proof(db, sub, now)
    rows = list(db.scalars(select(CreditTransaction).where(
        CreditTransaction.user_id == sub.user_id, CreditTransaction.subscription_id == sub.id,
        CreditTransaction.period_start == allocation.period_start,
        CreditTransaction.period_end == allocation.period_end).with_for_update()))
    if (sum(r.transaction_type == 'grant' for r in rows) != 1
            or any(type(r.credits_change) is not int
                   or r.transaction_type not in ('grant', 'spend', 'refund')
                   or (r.credits_change >= 0 if r.transaction_type == 'spend' else r.credits_change <= 0)
                   for r in rows)):
        raise HTTPException(503,'Paid credit ledger requires review.')
    remaining = sum(r.credits_change for r in rows)
    if not 0 <= remaining <= allocation.credits:
        raise HTTPException(503,'Paid credit ledger requires review.')
    return remaining, allocation.period_start, allocation.period_end


def require_settlement(db, subscription, now):
    from app.core.owner_plans import PAID_CODES
    if subscription is None:
        raise HTTPException(503, 'Original credit subscription is unavailable.')
    if subscription.plan_kind in PAID_CODES:
        # Expiry during an already-reserved generation is permitted; revocation is not.
        proof(db, subscription, now, settlement=True)
