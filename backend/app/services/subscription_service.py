"""Owner subscriptions, gated on migration 003; never activates paid plans."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.models.subscription_plan import SubscriptionPlan
from app.models.subscription import Subscription
from app.models.credit_transaction import CreditTransaction
from app.repositories.user_repository import lock_profile
from app.repositories.profile_repository import find_owner_profile, STUDIO_FIELDS
from app.schemas.owner import StudioUpdate
from app.services.onboarding_service import require_owner
from app.services.credit_service import balance

UNAVAILABLE = "Subscriptions are unavailable until the approved database migration is applied."


def require_schema(db):
    # No feature flag changes, DDL, auto-create or optimistic queries of absent columns.
    inspector = inspect(db.connection())
    for model in (SubscriptionPlan, Subscription, CreditTransaction):
        table = model.__table__
        if not inspector.has_table(table.name):
            raise HTTPException(503, UNAVAILABLE)
        columns = {c['name']: c for c in inspector.get_columns(table.name)}
        if not set(table.columns.keys()) <= columns.keys():
            raise HTTPException(503, UNAVAILABLE)
        for c in table.columns:
            if bool(columns[c.name]['nullable']) != bool(c.nullable):
                raise HTTPException(503, UNAVAILABLE)
            if c.computed is not None and not columns[c.name].get('computed', {}).get('persisted'):
                raise HTTPException(503, UNAVAILABLE)
        actual = {tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name)}
        actual.update(tuple(c['column_names']) for c in inspector.get_indexes(table.name) if c.get('unique'))
        expected = {tuple(c.columns.keys()) for c in table.constraints if isinstance(c, UniqueConstraint)}
        if not expected <= actual:
            raise HTTPException(503, UNAVAILABLE)
        actual_fks = {
            (tuple(f['constrained_columns']), f.get('referred_schema'), f['referred_table'],
             tuple(f['referred_columns']))
            for f in inspector.get_foreign_keys(table.name)
        }
        expected_fks = {
            (tuple(element.parent.name for element in constraint.elements),
             None, constraint.elements[0].target_fullname.split(".")[-2],
             tuple(element.target_fullname.split(".")[-1] for element in constraint.elements))
            for constraint in table.constraints if isinstance(constraint, ForeignKeyConstraint)
        }
        for local_columns, _, target_table, target_columns in expected_fks:
            if not any(
                actual_local == local_columns
                and actual_target == target_table
                and actual_columns == target_columns
                and (schema is None or schema == inspector.default_schema_name)
                for actual_local, schema, actual_target, actual_columns in actual_fks
            ):
                raise HTTPException(503, UNAVAILABLE)


def plans(db):
    rows = list(db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.user_role == 'owner', SubscriptionPlan.is_active.is_(True))))
    result = {p.code: p for p in rows if p.code in ('basic', 'trial', 'pro')}
    expected = [
        ('basic', 'Free Basic', 10, 0, None, 2, 3),
        ('trial', 'Free Trial', 100, 0, 14, 10, 20),
        ('pro', 'Paid Pro', 500, 1500, None, 50, 100),
    ]
    for code, name, credits, price, days, max_projects, max_links in expected:
        p = result.get(code)
        if (p is None or p.name != name or p.monthly_credits != credits or p.price != price
                or p.trial_days != days or p.currency != 'LKR'
                or p.max_projects != max_projects or p.max_share_links != max_links):
            raise HTTPException(503, "Subscription catalogue is unavailable.")
    return result


def catalogue(db, user):
    require_owner(user)
    require_schema(db)
    available = plans(db)
    return {'plans': [dict(code=p.code, name=p.name, currency=p.currency, price=str(p.price),
        credits=p.monthly_credits, credit_period='trial_total' if p.code == 'trial' else 'monthly_anniversary',
        trial_days=p.trial_days, max_projects=p.max_projects, max_share_links=p.max_share_links,
        activation_available=p.code in ('basic', 'trial')) for p in (available['basic'], available['trial'], available['pro'])]}


def clock():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def snapshot(db, user, action=None, key=None):
    """GET is read-only; POST persists lazy expiry and current-period grants atomically."""
    try:
        require_owner(user)
        require_schema(db)
        current = lock_profile(db, user.id)
        require_owner(current)
        profile = find_owner_profile(db, current.id, lock=True)
        if action:
            if not profile or profile.onboarding_status not in ('pending_plan', 'completed'):
                raise HTTPException(409, "Complete Studio Setup first.")
            try:
                StudioUpdate(**{k: getattr(profile, k) for k in STUDIO_FIELDS})
            except ValidationError:
                raise HTTPException(409, "Complete Studio Setup first.") from None
        available = plans(db)
        history = list(db.scalars(select(Subscription).where(Subscription.user_id == current.id)
                      .with_for_update().execution_options(populate_existing=True)))
        used = any(s.plan_kind == 'trial' for s in history)
        active_rows = [s for s in history if s.status == 'active']
        if len(active_rows) > 1:
            raise HTTPException(503, "Subscription state is unavailable.")
        active = active_rows[0] if active_rows else None
        now = clock()
        request_key = sha256(('request:' + key).encode()).digest() if key else None
        replay = next((s for s in history if s.activation_key == request_key), None) if key else None
        if replay and replay.plan_kind != action:
            raise HTTPException(409, "Idempotency key was already used for a different plan.")
        if action == 'trial' and used and not replay:
            raise HTTPException(409, "The free trial has already been used.")
        expired = active and active.end_date is not None and now >= active.end_date
        if expired:
            anchor = active.end_date
            previous = active
            if action:
                previous.status = 'expired'
                db.flush()
            active = Subscription(user_id=current.id, plan_id=available['basic'].id, plan_kind='basic',
                start_date=anchor, status='active', activation_key=sha256(f'fallback:{previous.id}'.encode()).digest())
            if action:
                db.add(active)
                db.flush()
        if active and active.plan_kind == 'pro':
            raise HTTPException(503, "Paid activation is not available.")
        if action == 'basic' and active and active.plan_kind == 'trial':
            raise HTTPException(409, "Your trial is active. Basic starts when it expires.")
        if action and not replay and (active is None or action == 'trial'):
            if active:
                active.status = 'superseded'
                db.flush()
            active = Subscription(user_id=current.id, plan_id=available[action].id, plan_kind=action,
                start_date=now, end_date=now + timedelta(days=14) if action == 'trial' else None,
                status='active', activation_key=request_key)
            db.add(active)
            db.flush()
        if not active:
            return {'plan': None, 'remaining_credits': 0, 'trial_available': not used, 'period_start': None, 'period_end': None}
        if active.id is None:  # Read-only virtual fallback, no persistent ledger yet.
            from app.services.credit_service import period
            remaining, (start, end) = 10, period(active, now)
        else:
            remaining, start, end = balance(db, active, now, grant=bool(action))
        if action:
            if profile.onboarding_status != 'completed':
                profile.onboarding_status = 'completed'
                profile.onboarding_completed_at = now
            db.commit()
        return {'plan': active.plan_kind, 'remaining_credits': remaining,
                'trial_available': not (used or active.plan_kind == 'trial'),
                'period_start': start, 'period_end': end}
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Subscription changed concurrently. Retry with the same idempotency key.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Subscriptions are temporarily unavailable.") from None
    except Exception:
        db.rollback()
        raise
