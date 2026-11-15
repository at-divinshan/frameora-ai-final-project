"""Read-only Normal User funded-period status; never resets the free allowance."""
from fastapi import HTTPException
from sqlalchemy import select
from app.core.stripe_test import require_release
from app.repositories.user_repository import lock_profile
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.services.paid_credit_service import balance
from app.services.subscription_service import clock


def status(db, user):
    if user.role != 'user': raise HTTPException(403,'Normal User access required.')
    require_release()
    try:
        current=lock_profile(db,user.id)
        if current is None or current.role!='user': raise HTTPException(403,'Account role changed.')
        rows=list(db.scalars(select(Subscription).where(Subscription.user_id==user.id,
            Subscription.status=='active').with_for_update()))
        if len(rows)>1: raise HTTPException(503,'Subscription state requires review.')
        sub=rows[0] if rows else None
        now=clock()
        if sub is None or (sub.end_date is not None and sub.end_date<=now):
            return {'plan':'free','remaining_credits':0,'paid_generation_available':False,
                    'free_allowance_preserved':True}
        plan=db.get(SubscriptionPlan,sub.plan_id)
        if plan is None or plan.user_role!='user' or plan.code not in ('starter','pro'):
            raise HTTPException(503,'Normal User paid plan is unavailable.')
        remaining,start,end=balance(db,sub,now)
        return {'plan':plan.code,'remaining_credits':remaining,'period_start':start,'period_end':end,
                'paid_generation_available':remaining >= 4,'credits_per_image':1,'credits_per_batch':4}
    finally:
        db.rollback()
