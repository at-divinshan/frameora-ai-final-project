"""Admin read-only payment reporting. No provider calls or credit mutations."""
from datetime import datetime, time, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, func, literal, union_all, and_, case
from app.models.payment import Payment as P
from app.models.payment_preparation import PaymentCheckout as C, PaidCreditAllocation as A, PaymentWebhookEvent as E
from app.models.user import User as U
from app.models.subscription import Subscription as S
from app.models.subscription_plan import SubscriptionPlan as Plan


def records():
    payments = select(literal('payment').label('kind'), P.id, P.user_id, U.name, U.email,
        U.role, func.coalesce(C.plan_code, Plan.code).label('plan'), P.created_at.label('date'),
        P.amount, C.currency, P.status, C.provider_payment_id.label('transaction_id'),
        C.id.label('checkout_id'), C.livemode, C.verified_at, C.revoked_at, P.subscription_id
    ).join(U, U.id == P.user_id).outerjoin(C, and_(C.payment_id == P.id, C.user_id == P.user_id)).outerjoin(
        S, and_(S.id == P.subscription_id, S.user_id == P.user_id)).outerjoin(Plan, Plan.id == S.plan_id)
    pending = select(literal('checkout'), C.id, C.user_id, U.name, U.email, U.role,
        C.plan_code, C.created_at, C.amount_minor / 100, C.currency,
        case((and_(C.state.in_(['pending','open']), C.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None)), 'expired'),
             (C.state.in_(['pending','open']), 'pending'), else_=C.state), C.provider_payment_id, C.id, C.livemode, C.verified_at,
        C.revoked_at, literal(None)).join(U, U.id == C.user_id).where(C.payment_id.is_(None))
    return union_all(payments, pending).subquery()


def filtered(r, filters):
    conditions = []
    for field in ('role', 'plan', 'status'):
        value = getattr(filters, field)
        if value: conditions.append(r.c[field] == value)
    if filters.date_from: conditions.append(r.c.date >= datetime.combine(filters.date_from, time.min))
    if filters.date_to: conditions.append(r.c.date < datetime.combine(filters.date_to + timedelta(days=1), time.min))
    return conditions


def item(row):
    result = dict(row)
    result.pop('user_id', None)
    result['amount'] = str(result['amount']) if result['amount'] is not None else None
    result['verified'] = bool(result['kind'] == 'payment' and result['verified_at'] and result['livemode'] is False)
    return result


def listing(db, filters):
    r = records(); conditions = filtered(r, filters)
    success = and_(r.c.kind == 'payment', r.c.status == 'succeeded', r.c.livemode.is_(False), r.c.verified_at.is_not(None))
    totals = db.execute(select(func.count().label('total'),
        func.sum(case((success, 1), else_=0)).label('successful'),
        func.sum(case((and_(success, r.c.currency == 'lkr'), r.c.amount), else_=0)).label('revenue'),
        func.sum(case((r.c.status == 'pending', 1), else_=0)).label('pending'),
        func.sum(case((r.c.status.in_(['failed','refunded','partially_refunded','disputed']), 1), else_=0)).label('failed_refunded')
    ).select_from(r).where(*conditions)).mappings().one()
    rows = db.execute(select(r).where(*conditions).order_by(r.c.date.desc(), r.c.kind, r.c.id.desc())
        .offset((filters.page-1)*20).limit(20)).mappings().all()
    return dict(items=[item(row) for row in rows], total=totals['total'], page=filters.page, page_size=20,
        summary={k: str(totals[k] or 0) if k == 'revenue' else int(totals[k] or 0)
                 for k in ('successful','revenue','pending','failed_refunded')})


def detail(db, kind, identifier):
    r=records()
    row=db.execute(select(r).where(r.c.kind==kind,r.c.id==identifier)).mappings().one_or_none()
    if row is None: raise HTTPException(404,'Payment record not found.')
    result=item(row)
    result.update(subscription=None, allocation=None, events=[])
    if row['subscription_id']:
        sub=db.execute(select(S.status,S.start_date,S.end_date).where(S.id==row['subscription_id'],S.user_id==row['user_id'])).mappings().one_or_none()
        result['subscription']=dict(sub) if sub else None
    if row['checkout_id']:
        allocation=db.execute(select(A.credits,A.period_start,A.period_end,A.revoked_at).where(
            A.checkout_id==row['checkout_id'],A.user_id==row['user_id'])).mappings().one_or_none()
        result['allocation']=dict(allocation) if allocation else None
        result['events']=[dict(e) for e in db.execute(select(E.event_type,E.outcome,E.processed_at,E.amount_minor,E.currency)
            .where(E.checkout_id==row['checkout_id']).order_by(E.processed_at.desc(),E.id.desc()).limit(50)).mappings().all()]
    return result
