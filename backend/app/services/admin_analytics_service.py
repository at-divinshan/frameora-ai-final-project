"""Read-only aggregate reporting; no entitlement reconciliation or provider calls."""
from datetime import datetime, timezone
from sqlalchemy import select, func, or_, exists
from sqlalchemy.exc import SQLAlchemyError
from app.models.user import User
from app.models.customer_project import CustomerProject
from app.models.photography_plan import PhotographyPlan
from app.models.media_asset import MediaAsset
from app.models.ai_generation import AIGeneration
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.payment import Payment
from app.models.payment_preparation import PaymentCheckout, PaidCreditAllocation


def verified_payments():
    p, c, a = Payment.__table__.c, PaymentCheckout.__table__.c, PaidCreditAllocation.__table__.c
    # EXISTS avoids multiplication by allocation rows or webhook deliveries.
    proof = exists(select(1).select_from(PaymentCheckout.__table__.join(
        PaidCreditAllocation.__table__, a.checkout_id == c.id)).where(
        c.payment_id == p.id, c.user_id == p.user_id, c.state == 'fulfilled',
        c.livemode.is_(False), c.verified_at.is_not(None), c.revoked_at.is_(None),
        c.provider_payment_id.is_not(None), c.currency == 'lkr',
        c.amount_minor == p.amount * 100, a.user_id == p.user_id,
        a.subscription_id == p.subscription_id, a.revoked_at.is_(None)))
    return select(p.id, p.amount, p.created_at).where(p.status == 'succeeded', proof).subquery()


def queries(now):
    u, pr, pl = User.__table__.c, CustomerProject.__table__.c, PhotographyPlan.__table__.c
    m, g = MediaAsset.__table__.c, AIGeneration.__table__.c
    s, plan = Subscription.__table__.c, SubscriptionPlan.__table__.c
    p = verified_payments()
    month = lambda col: func.date_format(col, '%Y-%m')
    return {
        'users': select(func.count()).select_from(User.__table__),
        'owners': select(func.count()).select_from(User.__table__).where(u.role == 'owner'),
        # Standalone photography plans plus real project containers, never their child plans twice.
        'projects': select((select(func.count()).select_from(CustomerProject.__table__).where(pr.deleted_at.is_(None)).scalar_subquery()
            + select(func.count()).select_from(PhotographyPlan.__table__).where(pl.project_id.is_(None)).scalar_subquery())),
        'images': select(func.count()).select_from(MediaAsset.__table__.join(AIGeneration.__table__, m.generation_id == g.id)).where(
            m.user_id == g.user_id, m.asset_type == 'ai_generated', g.status == 'completed'),
        'image_trend': select(month(g.completed_at).label('month'), func.count().label('value')).select_from(
            MediaAsset.__table__.join(AIGeneration.__table__, m.generation_id == g.id)).where(
            m.user_id == g.user_id, m.asset_type == 'ai_generated', g.status == 'completed',
            g.completed_at.is_not(None)).group_by(month(g.completed_at)).order_by(month(g.completed_at).desc()).limit(12),
        'subscriptions': select(plan.user_role.label('role'), plan.name.label('plan'), func.count().label('count')).select_from(
            Subscription.__table__.join(SubscriptionPlan.__table__, s.plan_id == plan.id)).where(
            s.status == 'active', s.start_date <= now, or_(s.end_date.is_(None), s.end_date > now)
        ).group_by(plan.user_role, plan.id, plan.name).order_by(plan.user_role, plan.name),
        'payments': select(func.count()).select_from(p),
        'revenue': select(func.coalesce(func.sum(p.c.amount), 0)),
        'payment_trend': select(month(p.c.created_at).label('month'), func.sum(p.c.amount).label('value')).where(
            p.c.created_at.is_not(None)).group_by(month(p.c.created_at)).order_by(month(p.c.created_at).desc()).limit(12),
        'registration_trend': select(month(u.created_at).label('month'), func.count().label('value')).where(
            u.created_at.is_not(None)).group_by(month(u.created_at)).order_by(month(u.created_at).desc()).limit(12),
    }


def analytics(db):
    result = {}
    for name, query in queries(datetime.now(timezone.utc).replace(tzinfo=None)).items():
        try:
            if name in ('subscriptions', 'payment_trend', 'registration_trend', 'image_trend'):
                rows = [dict(row) for row in db.execute(query).mappings().all()]
                result[name] = rows if name == 'subscriptions' else list(reversed(rows))
            else:
                result[name] = db.scalar(query)
        except SQLAlchemyError:
            db.rollback()
            result[name] = None  # Missing schema/connectivity is never represented as zero.
    return result
