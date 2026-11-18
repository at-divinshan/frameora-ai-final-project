"""Prepared v4 persistence. No auto-DDL. Called only behind the payment release gate.

User locks serialize checkout, fulfillment, refunds and existing generation debits.
Each local transition commits once; provider calls never occur inside these locks.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError
from app.models.user import User
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.credit_transaction import CreditTransaction
from app.models.payment import Payment
from app.models.payment_preparation import PaymentCheckout, PaymentWebhookEvent, PaidCreditAllocation
from app.core.stripe_prices import paid_plan, purchase_plan
from app.services.credit_service import anniversary
from app.repositories.user_repository import lock_profile
from app.repositories.profile_repository import find_owner_profile


def clock(): return datetime.now(timezone.utc).replace(tzinfo=None,microsecond=0)

def key(text): return sha256(text.encode()).digest()

class PaymentRepository:
    def __init__(self, db): self.db=db

    @contextmanager
    def transaction(self):
        try:
            yield
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise HTTPException(503,'Payment state could not be confirmed. Retry safely with the same key.') from None
        except Exception:
            self.db.rollback()
            raise

    def get_purchase(self, identifier):
        row=self.db.get(PaymentCheckout,identifier)
        if row is None: raise HTTPException(409,'Payment purchase is not yet available. Retry delivery.')
        # Detach a snapshot before releasing the read transaction/provider network work.
        from types import SimpleNamespace
        snapshot=SimpleNamespace(**{c.name:getattr(row,c.name) for c in PaymentCheckout.__table__.columns})
        plan=self.db.get(SubscriptionPlan,row.plan_id)
        if plan is None: raise HTTPException(503,'Purchase plan is unavailable.')
        snapshot.role=plan.user_role
        purchase_plan(snapshot)
        self.db.rollback()
        return snapshot

    def _plan(self, code, role='owner'):
        expected=paid_plan(role,code)
        plan=self.db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code==code,
            SubscriptionPlan.user_role==role,SubscriptionPlan.is_active.is_(True)))
        if (plan is None or plan.name!=expected.name or plan.monthly_credits!=expected.credits
                or plan.price*100!=expected.amount_minor or plan.currency!='LKR'
                or plan.max_projects!=expected.max_projects or plan.max_share_links!=expected.max_share_links
                or plan.trial_days is not None):
            raise HTTPException(503,'Paid catalogue has not been verified.')
        return plan

    def _active(self, user_id):
        rows=list(self.db.scalars(select(Subscription).where(Subscription.user_id==user_id,
            Subscription.status=='active').with_for_update().execution_options(populate_existing=True)))
        if len(rows)>1: raise HTTPException(503,'Subscription state requires review.')
        return rows[0] if rows else None

    def reserve_purchase(self, user, request):
        from app.services.payment_service import prepare_intent
        intent=prepare_intent(user,request)
        with self.transaction():
            current=lock_profile(self.db,user.id)
            if current is None or current.role != user.role:
                raise HTTPException(403,'Account role changed. Sign in again.')
            approved=paid_plan(current.role,request.plan_code)
            if current.role=='owner':
                profile=find_owner_profile(self.db,current.id,lock=True)
                if not profile or profile.onboarding_status!='completed':
                    raise HTTPException(409,'Complete studio onboarding first.')
            request_key=key(f'checkout:{user.id}:{request.idempotency_key}')
            digest=key(f'{current.role}:{approved.price_id}:{intent.plan_code}:{intent.currency}:{intent.amount_minor}:{intent.credits}')
            purchase=self.db.scalar(select(PaymentCheckout).where(PaymentCheckout.user_id==user.id,
                PaymentCheckout.request_key==request_key).with_for_update())
            now=clock()
            if purchase:
                if purchase.request_hash!=digest: raise HTTPException(409,'Checkout key was used for different inputs.')
                if purchase.expires_at<=now: raise HTTPException(409,'Checkout expired. Start a new purchase.')
            else:
                active=self._active(user.id)
                if active and active.plan_kind!='basic' and (active.end_date is None or active.end_date>now):
                    raise HTTPException(409,'Wait until the current trial or paid period ends before purchasing.')
                pending=self.db.scalar(select(PaymentCheckout.id).where(PaymentCheckout.user_id==user.id,
                    PaymentCheckout.state.in_(('pending','open','review')),
                    or_(PaymentCheckout.state=='review',PaymentCheckout.expires_at>now)))
                if pending: raise HTTPException(409,'An existing checkout is pending. Retry its original request.')
                plan=self._plan(intent.plan_code,current.role)
                purchase=PaymentCheckout(user_id=user.id,plan_id=plan.id,plan_code=intent.plan_code,
                    request_key=request_key,request_hash=digest,amount_minor=intent.amount_minor,
                    currency=intent.currency,credits=intent.credits,state='pending',livemode=False,
                    created_at=now,expires_at=now+timedelta(hours=1))
                self.db.add(purchase); self.db.flush()
            identifier=purchase.id
        return self.get_purchase(identifier)

    def bind_session(self, snapshot, session_id):
        with self.transaction():
            current=lock_profile(self.db,snapshot.user_id)
            if current is None or current.role!=snapshot.role:
                raise HTTPException(403,'Purchase account role changed.')
            purchase=self.db.get(PaymentCheckout,snapshot.id,populate_existing=True,with_for_update=True)
            if purchase.provider_session_id not in (None,session_id): raise HTTPException(409,'Checkout session conflict.')
            purchase.provider_session_id=session_id
            if purchase.state=='pending': purchase.state='open'

    def apply_event(self, event, payload_hash, verified):
        snapshot=self.get_purchase(verified.checkout_id)
        with self.transaction():
            # Refunds must also revoke disabled accounts; never require login here.
            user=self.db.get(User,snapshot.user_id,populate_existing=True,with_for_update=True)
            if user is None: raise HTTPException(409,'Payment account is unavailable.')
            purchase=self.db.get(PaymentCheckout,snapshot.id,populate_existing=True,with_for_update=True)
            existing=self.db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_id==event['id']))
            if existing:
                if existing.checkout_id!=purchase.id or existing.payload_hash!=payload_hash:
                    raise HTTPException(409,'Webhook identity conflict.')
                return {'received':True,'outcome':existing.outcome}
            if (purchase.livemode or purchase.user_id!=snapshot.user_id
                    or purchase.amount_minor!=verified.amount_minor or purchase.currency!=verified.currency
                    or purchase.provider_payment_id not in (None,verified.payment_intent_id)
                    or purchase.provider_session_id not in (None,verified.session_id)):
                raise HTTPException(409,'Saved payment identity conflict.')
            now=clock()
            purchase.provider_payment_id=verified.payment_intent_id
            if verified.session_id: purchase.provider_session_id=verified.session_id
            # A pre-fulfillment refund cannot be undone by a delayed success event.
            if purchase.state=='revoked' and not verified.reversal:
                outcome='revoked'
            elif verified.reversal:
                self._revoke(purchase,verified.reversal_reason or 'refund_or_dispute',now)
                outcome='revoked'
            elif purchase.state in ('fulfilled','review'):
                outcome=purchase.state
            else:
                outcome=self._fulfill(user,purchase,verified,now)
            self.db.add(PaymentWebhookEvent(event_id=event['id'],event_type=event['type'],
                payload_hash=payload_hash,livemode=False,checkout_id=purchase.id,
                received_at=now,processed_at=now,outcome=outcome,provider_object_id=event['data']['object']['id'],
                amount_minor=verified.reversal_amount if verified.reversal else verified.amount_minor,currency=verified.currency))
            self.db.flush()
        return {'received':True,'outcome':outcome}

    def _record_payment(self,purchase,status,now,subscription_id=None):
        if purchase.payment_id:
            payment=self.db.get(Payment,purchase.payment_id,with_for_update=True)
        else:
            payment=Payment(user_id=purchase.user_id,subscription_id=subscription_id,
                amount=Decimal(purchase.amount_minor)/100,status=status,created_at=now)
            self.db.add(payment); self.db.flush(); purchase.payment_id=payment.id
        # Out-of-order refund events must not erase a stronger recorded reversal.
        priority={'partially_refunded':1,'refunded':2,'disputed':3}
        if priority.get(status,0) >= priority.get(payment.status,0):
            payment.status=status
        return payment

    def _fulfill(self,user,purchase,verified,now):
        from app.core.account_state import require_active
        try:
            plan=self.db.get(SubscriptionPlan,purchase.plan_id)
            if plan is None or user.role!=plan.user_role or user.role not in ('owner','user'):
                raise HTTPException(403,'Purchase account role changed.')
            require_active(self.db,user,None)
        except HTTPException as exc:
            if exc.status_code not in (401,403): raise
            self._record_payment(purchase,'review',now); purchase.state='review'
            return 'review'
        plan=self._plan(purchase.plan_code,user.role)
        if plan.id!=purchase.plan_id:
            raise HTTPException(409,'Purchase plan identity changed.')
        active=self._active(user.id)
        if active and active.plan_kind!='basic' and (active.end_date is None or active.end_date>now):
            self._record_payment(purchase,'review',now); purchase.state='review'
            return 'review'
        start=verified.paid_at; end=anniversary(start,1)
        if start>now: raise HTTPException(409,'Payment date is in the future.')
        if active and end>now:
            active.status='expired' if active.end_date is not None and active.end_date<=now else 'superseded'
            self.db.flush()
        subscription=Subscription(user_id=user.id,plan_id=purchase.plan_id,plan_kind=purchase.plan_code,
            start_date=start,end_date=end,status='active' if end>now else 'expired',
            activation_key=key(f'paid:{purchase.id}'))
        self.db.add(subscription); self.db.flush()
        grant_key=key(f'paid-grant:{purchase.id}')
        grant=CreditTransaction(user_id=user.id,subscription_id=subscription.id,generation_id=None,
            credits_change=purchase.credits,transaction_type='grant',created_at=now,
            period_start=start,period_end=end,operation_key=grant_key,request_hash=purchase.request_hash)
        self.db.add(grant); self.db.flush()
        self.db.add(PaidCreditAllocation(user_id=user.id,checkout_id=purchase.id,
            subscription_id=subscription.id,grant_transaction_id=grant.id,credits=purchase.credits,
            period_start=start,period_end=end,created_at=now))
        self._record_payment(purchase,'succeeded',now,subscription.id)
        purchase.state='fulfilled'; purchase.verified_at=now
        return 'fulfilled'

    def _revoke(self,purchase,reason,now):
        purchase.state='revoked'; purchase.revoked_at=purchase.revoked_at or now
        self._record_payment(purchase,'disputed' if reason=='dispute' else 'partially_refunded' if reason=='partial_refund' else 'refunded',now)
        allocation=self.db.scalar(select(PaidCreditAllocation).where(PaidCreditAllocation.checkout_id==purchase.id).with_for_update())
        if allocation:
            allocation.revoked_at=allocation.revoked_at or now
            subscription=self.db.get(Subscription,allocation.subscription_id,with_for_update=True)
            if subscription.status=='active':
                subscription.status='cancelled'; self.db.flush()
                original_plan=self.db.get(SubscriptionPlan,purchase.plan_id)
                if original_plan is None: raise HTTPException(503,'Purchase plan unavailable.')
                if original_plan.user_role=='user':
                    return  # Preserve the Normal User lifetime free allowance; no Basic owner plan.
                basic=self.db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code=='basic',SubscriptionPlan.user_role=='owner'))
                if basic is None: raise HTTPException(503,'Free Basic fallback is unavailable.')
                self.db.add(Subscription(user_id=purchase.user_id,plan_id=basic.id,plan_kind='basic',
                    start_date=now,end_date=None,status='active',activation_key=key(f'revoked:{purchase.id}')))
        # Retain all historical grants/spends/refunds. Revoked proof blocks their use.
