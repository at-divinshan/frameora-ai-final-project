"""Owner entitlements shared by read endpoints and serialized credit writers."""

from fastapi import HTTPException
from sqlalchemy import select

from app.models.subscription import Subscription
from app.repositories.profile_repository import find_owner_profile
from app.repositories.user_repository import lock_profile
from app.services import credit_service, subscription_service as subscriptions
from app.services.onboarding_service import require_owner

from app.core.owner_generation_config import BATCH_SIZE

BATCH_COST = BATCH_SIZE


def resolve_locked(db, user, *, now, persist=False, grant=False):
    """Caller owns transaction; always lock User before subscription/ledger rows."""
    require_owner(lock_profile(db, user.id))
    subscriptions.require_schema(db)
    available = subscriptions.plans(db)
    history = list(db.scalars(select(Subscription).where(Subscription.user_id == user.id)
        .execution_options(populate_existing=True).with_for_update()))
    active_rows = [row for row in history if row.status == 'active']
    if len(active_rows) > 1:
        raise HTTPException(503, "Subscription state is unavailable.")
    stored = active_rows[0] if active_rows else None
    if stored and (stored.plan_kind not in available or stored.plan_id != available[stored.plan_kind].id
                   or stored.start_date > now):
        raise HTTPException(503, "Subscription state is unavailable.")
    expired = bool(stored and stored.end_date is not None and now >= stored.end_date)
    # Pro stays unavailable, even if inserted by another system. No paid activation here.
    active = subscriptions.resolve_effective(db, user.id, stored, available, now, persist=persist)
    profile = find_owner_profile(db, user.id)
    ready = bool(profile and profile.onboarding_status == 'completed')
    remaining, start, end = 0, None, None
    renewal_due = False
    allowed_plan = active is not None and active.plan_kind in ('basic', 'trial')
    if allowed_plan:
        if active.id is None:
            remaining = available['basic'].monthly_credits
            start, end = credit_service.period(active, now)
            renewal_due = True
        else:
            from app.models.credit_transaction import CreditTransaction
            start, end = credit_service.period(active, now)
            granted = db.scalar(select(CreditTransaction.id).where(
                CreditTransaction.user_id == user.id, CreditTransaction.subscription_id == active.id,
                CreditTransaction.transaction_type == 'grant', CreditTransaction.period_start == start))
            renewal_due = active.plan_kind == 'basic' and granted is None
            remaining, start, end = credit_service.balance(db, active, now, grant=grant and ready)
    can_generate = allowed_plan and ready and remaining >= BATCH_COST
    reason = ('subscription_required' if active is None else 'paid_activation_disabled'
              if not allowed_plan else 'onboarding_required' if not ready else
              'insufficient_credits' if remaining < BATCH_COST else None)
    result = dict(
        plan=active.plan_kind if active else None,
        status='active' if allowed_plan else 'unavailable',
        previous_subscription_expired=expired,
        source_status='expired' if expired else 'active' if stored and stored.plan_kind in ('basic', 'trial') else 'unavailable',
        subscription_id=active.id if active else None,
        subscription_start=active.start_date if active else None,
        subscription_end=active.end_date if active else None,
        remaining_credits=remaining, period_start=start, period_end=end,
        monthly_renewal_due=renewal_due, generation_allowed=can_generate,
        batch_cost=BATCH_COST, reason=reason,
        trial_available=not any(row.plan_kind == 'trial' for row in history),
        max_projects=available[active.plan_kind].max_projects if active else 0,
        max_share_links=available[active.plan_kind].max_share_links if active else 0,
    )
    return active, result


def read(db, user):
    try:
        _, result = resolve_locked(db, user, now=subscriptions.clock())
        return result
    finally:
        db.rollback()  # Read-only response never grants, activates or expires records.
