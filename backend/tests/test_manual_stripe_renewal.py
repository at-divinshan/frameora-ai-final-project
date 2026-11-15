"""Manual renewals against in-memory rows and mocked Stripe HTTP; no SQL executed."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy.sql.elements import BindParameter, BooleanClauseList, Grouping, True_, False_
from sqlalchemy.sql import operators
from fastapi import HTTPException
from app.core import stripe_test
from app.core.stripe_prices import paid_plan
from app.models.user import User
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.credit_transaction import CreditTransaction
from app.models.payment import Payment
from app.models.payment_preparation import PaidCreditAllocation, PaymentCheckout
from app.models.free_generation_allowance import FreeGenerationAllowance
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import UserCheckoutRequest, OwnerCheckoutRequest
from app.services.payment_processing import process_event
from app.services import paid_credit_service, subscription_service
from test_stripe_preparation import MemorySession, NOW, provider
from test_stripe_role_prices import role_objects

PLANS = [('user','starter',40),('user','pro',100),('owner','starter',100),
         ('owner','growth',250),('owner','unlimited',500)]

class RenewalSession(MemorySession):
    """Evaluate WHERE expressions, including expiry inequalities/OR, without a DB."""
    def _matching(self, statement):
        kind=statement.column_descriptions[0]['entity']
        def value(expr,row):
            if isinstance(expr,BindParameter): return expr.value
            if isinstance(expr,True_): return True
            if isinstance(expr,False_): return False
            if isinstance(expr,Grouping): return value(expr.element,row)
            if isinstance(expr,BooleanClauseList):
                values=[value(c,row) for c in expr.clauses]
                return all(values) if expr.operator is operators.and_ else any(values)
            if hasattr(expr,'left'):
                left,right=value(expr.left,row),value(expr.right,row)
                if expr.operator is operators.in_op: return left in right
                if expr.operator is operators.is_: return left is right
                return expr.operator(left,right)
            return getattr(row,expr.key)
        return [row for row in self.rows.get(kind,[])
                if all(value(c,row) for c in statement._where_criteria)]

class ManualRenewalTests(unittest.TestCase):
    def setup_account(self,role,code):
        db=RenewalSession(); user=User(id=7,role=role,name='Fixture',email='fixture@example.invalid')
        db.add(user); plan=paid_plan(role,code)
        db.add(SubscriptionPlan(id=12,user_role=role,code=code,name=plan.name,is_active=True,
            price=plan.amount_minor/100,currency='LKR',monthly_credits=plan.credits,
            max_projects=plan.max_projects,max_share_links=plan.max_share_links))
        # Preserve this exact object/history; payments must never reset lifetime usage.
        free=FreeGenerationAllowance(user_id=7,state='consumed',generation_id=91,
            reserved_at=NOW-timedelta(days=10),consumed_at=NOW-timedelta(days=10))
        db.rows[FreeGenerationAllowance]=[free]
        self.free_snapshot={c.name:getattr(free,c.name) for c in free.__table__.columns}
        return db,user,PaymentRepository(db)

    def reserve(self,repo,user,code,now,key):
        request=(UserCheckoutRequest if user.role=='user' else OwnerCheckoutRequest)(plan_code=code,idempotency_key=key*32)
        with patch('app.repositories.payment_repository.lock_profile',return_value=user), \
             patch('app.repositories.payment_repository.find_owner_profile',return_value=SimpleNamespace(onboarding_status='completed')), \
             patch('app.repositories.payment_repository.clock',return_value=now):
            return repo.reserve_purchase(user,request)

    def remote_event(self,p,paid_at,event_id):
        data=role_objects(p)
        # Distinct Session/Intent/Charge IDs for each independent manual purchase.
        sid=f'cs_test_{p.id}'; pi=f'pi_{p.id}'; charge=f'ch_{p.id}'
        session=data.pop('checkout/sessions/cs_test_mock')
        session.update(id=sid,client_reference_id=str(p.id),payment_intent=pi)
        data['checkout/sessions/'+sid]=session
        data['checkout/sessions/'+sid+'/line_items']=data.pop('checkout/sessions/cs_test_mock/line_items')
        intent=data.pop('payment_intents/pi_mock');intent.update(id=pi,latest_charge=charge)
        data['payment_intents/'+pi]=intent
        obj=data.pop('charges/ch_mock');obj.update(id=charge,payment_intent=pi,
            created=int(paid_at.replace(tzinfo=timezone.utc).timestamp()))
        data['charges/'+charge]=obj
        event={'id':event_id,'type':'checkout.session.completed','livemode':False,
               'data':{'object':{'id':sid,'metadata':{'checkout_id':str(p.id)}}}}
        return data,event

    def deliver(self,repo,data,event,now):
        with patch('app.core.account_state.require_active'),patch('app.repositories.payment_repository.clock',return_value=now):
            return process_event(event,json.dumps(event).encode(),repo,provider(data))

    def assert_free_unchanged(self,db):
        free=db.rows[FreeGenerationAllowance][0]
        self.assertEqual({c.name:getattr(free,c.name) for c in free.__table__.columns},self.free_snapshot)

    def test_two_manual_periods_all_plans_with_stale_active_or_expired_status(self):
        for role,code,credits in PLANS:
            for expired_status in ('active','expired'):
                with self.subTest(role=role,plan=code,expired_status=expired_status):
                    db,user,repo=self.setup_account(role,code)
                    first=self.reserve(repo,user,code,NOW,'a')
                    self.assertNotIn(CreditTransaction,db.rows)
                    data,event=self.remote_event(first,NOW,'evt_first')
                    self.assertEqual(self.deliver(repo,data,event,NOW)['outcome'],'fulfilled')
                    old=db.rows[Subscription][0]
                    self.assertEqual((old.status,db.rows[CreditTransaction][0].credits_change),('active',credits))
                    self.assertEqual(old.end_date,datetime(2026,12,14,8))
                    with self.assertRaises(HTTPException) as error:
                        self.reserve(repo,user,code,old.end_date-timedelta(seconds=1),'b')
                    self.assertEqual(error.exception.status_code,409)
                    old.status=expired_status
                    renewal_at=old.end_date  # Inclusive expiry boundary.
                    second=self.reserve(repo,user,code,renewal_at,'b')
                    self.assertNotEqual(first.id,second.id)
                    self.assertEqual(len(db.rows[CreditTransaction]),1)  # Checkout alone grants nothing.
                    second_data,second_event=self.remote_event(second,renewal_at,'evt_second')
                    self.deliver(repo,second_data,second_event,renewal_at)
                    new=db.rows[Subscription][-1]
                    self.assertEqual((old.status,new.status,new.start_date),('expired','active',renewal_at))
                    self.assertEqual(len(db.rows[Subscription]),2)
                    self.assertNotEqual(old.activation_key,new.activation_key)
                    self.assertEqual([r.credits_change for r in db.rows[CreditTransaction]],[credits,credits])
                    self.assertEqual(len(db.rows[Payment]),2)
                    self.assertEqual(len(db.rows[PaidCreditAllocation]),2)
                    self.assertEqual(len({p.provider_payment_id for p in db.rows[PaymentCheckout]}),2)
                    allocation=db.rows[PaidCreditAllocation][-1]
                    # Exercise actual period-scoped ledger selection, with proof already tested by independent payment retrieval.
                    with patch.object(paid_credit_service,'proof',return_value=allocation):
                        remaining,start,end=paid_credit_service.balance(db,new,renewal_at)
                    self.assertEqual(remaining,credits)  # Entire unused first grant remains historical, not spendable.
                    self.assertEqual((start,end),(new.start_date,new.end_date))
                    for duplicate_data,duplicate_event in [(data,event),(second_data,second_event),
                        (second_data,{**second_event,'id':'evt_second_another_delivery'})]:
                        self.deliver(repo,duplicate_data,duplicate_event,renewal_at)
                    self.assertEqual(len(db.rows[CreditTransaction]),2)
                    self.assertEqual(len(db.rows[Subscription]),2)
                    self.assert_free_unchanged(db)

    def test_unsuccessful_or_unverified_first_and_renewal_payments_grant_nothing(self):
        for role,code,_ in PLANS:
            for renewal in (False,True):
                with self.subTest(role=role,code=code,renewal=renewal):
                    db,user,repo=self.setup_account(role,code)
                    p=self.reserve(repo,user,code,NOW,'a');now=NOW
                    if renewal:
                        data,event=self.remote_event(p,now,'evt_initial');self.deliver(repo,data,event,now)
                        now=db.rows[Subscription][0].end_date
                        p=self.reserve(repo,user,code,now,'b')
                    baseline=(len(db.rows.get(Subscription,[])),len(db.rows.get(CreditTransaction,[])))
                    for kind in ('unpaid','failed_intent','uncaptured','wrong_amount'):
                        data,event=self.remote_event(p,now,'evt_bad_'+kind)
                        if kind=='unpaid': data[f'checkout/sessions/cs_test_{p.id}']['payment_status']='unpaid'
                        elif kind=='failed_intent': data[f'payment_intents/pi_{p.id}']['status']='requires_payment_method'
                        elif kind=='uncaptured': data[f'charges/ch_{p.id}']['captured']=False
                        else: data[f'payment_intents/pi_{p.id}']['amount_received']=1
                        with self.assertRaises(HTTPException): self.deliver(repo,data,event,now)
                        self.assertEqual((len(db.rows.get(Subscription,[])),len(db.rows.get(CreditTransaction,[]))),baseline)
                    self.assert_free_unchanged(db)

    def test_owner_basic_fallback_can_be_replaced_by_manual_payment(self):
        for role,code,credits in PLANS[2:]:
            with self.subTest(plan=code):
                db,user,repo=self.setup_account(role,code)
                p=self.reserve(repo,user,code,NOW,'a');data,event=self.remote_event(p,NOW,'evt_first')
                self.deliver(repo,data,event,NOW);old=db.rows[Subscription][0]
                basic=SubscriptionPlan(id=10,code='basic',user_role='owner')
                db.add(basic)
                fallback=subscription_service.resolve_effective(db,user.id,old,{'basic':basic},old.end_date,persist=True)
                p=self.reserve(repo,user,code,old.end_date,'b');data,event=self.remote_event(p,old.end_date,'evt_renewal')
                self.deliver(repo,data,event,old.end_date)
                self.assertEqual((old.status,fallback.status),('expired','superseded'))
                self.assertEqual(len(db.rows[Subscription]),3)
                self.assertEqual([r.credits_change for r in db.rows[CreditTransaction]],[credits,credits])
                self.assert_free_unchanged(db)

    @patch('app.core.stripe_test.RELEASE_VERIFIED', False)
    @patch('app.core.stripe_test.STRIPE_TEST_ENABLED', False)
    def test_payment_gates_remain_disabled(self):
        self.assertFalse(stripe_test.RELEASE_VERIFIED)
        self.assertFalse(stripe_test.STRIPE_TEST_ENABLED)
