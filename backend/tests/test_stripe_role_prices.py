"""Role-specific sandbox checkout tests; no engine, SQL or real provider calls."""
import unittest
from urllib.parse import parse_qs
from types import SimpleNamespace
from unittest.mock import patch, Mock
from datetime import timedelta
from fastapi import HTTPException
from app.core.stripe_prices import PRICE_IDS, paid_plan, checkout_metadata
from app.core import stripe_test
from app.schemas.payment import UserCheckoutRequest, OwnerCheckoutRequest
from app.services.payment_service import prepare_intent
from app.services.payment_processing import verify_paid
from app.models.payment_preparation import PaymentCheckout, PaidCreditAllocation
from app.models.subscription_plan import SubscriptionPlan
from app.models.subscription import Subscription
from app.models.credit_transaction import CreditTransaction
from app.models.payment import Payment
from app.models.user import User
from app.repositories.payment_repository import PaymentRepository
from test_stripe_preparation import purchase, objects, provider, event, MemorySession, NOW


def role_purchase(role,code):
    p=purchase(); p.role=role; p.plan_code=code
    plan=paid_plan(role,code); p.amount_minor=plan.amount_minor; p.credits=plan.credits
    return p


def role_objects(p):
    data=objects(); plan=paid_plan(p.role,p.plan_code)
    price={**data['prices/'+PRICE_IDS[('owner','starter')]],'id':plan.price_id,'unit_amount':plan.amount_minor}
    data['prices/'+plan.price_id]=price
    session=data['checkout/sessions/cs_test_mock']; intent=data['payment_intents/pi_mock']; charge=data['charges/ch_mock']
    session.update(metadata=checkout_metadata(p),amount_total=plan.amount_minor)
    intent.update(metadata=checkout_metadata(p),amount=plan.amount_minor,amount_received=plan.amount_minor)
    charge.update(amount=plan.amount_minor)
    data['checkout/sessions/cs_test_mock/line_items']['data'][0].update(price=price,amount_total=plan.amount_minor,amount_subtotal=plan.amount_minor)
    return data

class RolePriceTests(unittest.TestCase):
    def test_checkout_uses_dashboard_payment_methods_for_all_paid_plans(self):
        for role, code in PRICE_IDS:
            with self.subTest(role=role, code=code):
                p = role_purchase(role, code)
                data = role_objects(p)
                data['checkout/sessions'] = {
                    **data['checkout/sessions/cs_test_mock'],
                    'status': 'open', 'url': 'https://checkout.stripe.com/c/pay/mock',
                }
                seen = []
                provider(data, seen).create_checkout(p)
                request = seen[-1]
                self.assertEqual(request.method, 'POST')
                self.assertEqual(request.url.path, '/v1/checkout/sessions')
                fields = parse_qs(request.content.decode())
                self.assertFalse(any(key == 'payment_method_types' or key.startswith('payment_method_types[') for key in fields))
                self.assertEqual(fields['mode'], ['payment'])
                self.assertEqual(fields['line_items[0][quantity]'], ['1'])
                self.assertEqual(fields['line_items[0][price]'], [PRICE_IDS[(role, code)]])
                self.assertEqual(request.headers['Stripe-Version'], stripe_test.API_VERSION)

    def test_all_five_ids_amounts_and_credits(self):
        expected={('user','starter'):(49000,40),('user','pro'):(99000,100),
                  ('owner','starter'):(150000,100),('owner','growth'):(250000,250),('owner','unlimited'):(350000,500)}
        for (role,code),(amount,credits) in expected.items():
            request=(UserCheckoutRequest if role=='user' else OwnerCheckoutRequest)(plan_code=code,idempotency_key='a'*32)
            intent=prepare_intent(SimpleNamespace(id=7,role=role),request)
            self.assertEqual((intent.amount_minor,intent.credits),(amount,credits))
            p=role_purchase(role,code); data=role_objects(p)
            data['checkout/sessions']={**data['checkout/sessions/cs_test_mock'],'status':'open','url':'https://checkout.stripe.com/c/pay/mock'}
            seen=[]; remote=provider(data,seen); remote.create_checkout(p)
            payload=seen[-1].content.decode()
            self.assertIn(PRICE_IDS[(role,code)],payload); self.assertNotIn('price_data',payload)
            self.assertIn('mode=payment',payload); self.assertNotIn('recurring',payload)
            self.assertIn('%2F'+role+'%2Fsubscription',payload)
            self.assertEqual(verify_paid(remote,p,'cs_test_mock').amount_minor,amount)

    def test_invalid_prices_and_cross_role_lines_fail_closed(self):
        p=role_purchase('user','starter')
        for field,value in [('livemode',True),('currency','usd'),('unit_amount',150000),('type','recurring'),('active',False)]:
            data=role_objects(p); data['prices/'+PRICE_IDS[('user','starter')]][field]=value
            with self.assertRaises(HTTPException): provider(data).create_checkout(p)
        data=role_objects(p)
        data['checkout/sessions/cs_test_mock/line_items']['data'][0]['price']['id']=PRICE_IDS[('owner','starter')]
        with self.assertRaises(HTTPException): verify_paid(provider(data),p,'cs_test_mock')
        data=role_objects(p); data['payment_intents/pi_mock']['metadata']['role']='owner'
        with self.assertRaises(HTTPException): verify_paid(provider(data),p,'cs_test_mock')

    def test_normal_fulfillment_refund_and_duplicate_leave_free_usage_untouched(self):
        for code in ['starter','pro']:
            db=MemorySession(); p=role_purchase('user',code); plan=paid_plan('user',code)
            row=PaymentCheckout(**{k:v for k,v in vars(p).items() if k!='role'}); db.add(row)
            db.add(User(id=7,name='Customer',email='mock@example.test',role='user',is_verified=True))
            db.add(SubscriptionPlan(id=12,code=code,name=plan.name,user_role='user',is_active=True,
                monthly_credits=plan.credits,price=plan.amount_minor/100,currency='LKR',max_projects=None,max_share_links=None))
            repo=PaymentRepository(db); proof=verify_paid(provider(role_objects(p)),p,'cs_test_mock')
            with patch('app.core.account_state.require_active'),patch('app.repositories.payment_repository.clock',return_value=NOW):
                repo.apply_event(event(),b'a'*32,proof)
                repo.apply_event(event(),b'a'*32,proof)
                self.assertEqual(len(db.rows[Subscription]),1)
                self.assertEqual(db.rows[CreditTransaction][0].credits_change,plan.credits)
                self.assertEqual(db.rows[Subscription][0].plan_kind,code)
                from dataclasses import replace
                repo.apply_event(event('refund.updated','evt_refund'),b'b'*32,replace(proof,reversal=True,reversal_reason='refund'))
                self.assertEqual(db.rows[Subscription][0].status,'cancelled')
                self.assertEqual(len(db.rows[Subscription]),1)  # Never an Owner Basic fallback.
                self.assertEqual(len(db.rows[CreditTransaction]),1)
                repo.apply_event(event(identifier='evt_late'),b'c'*32,proof)
                self.assertEqual(len(db.rows[CreditTransaction]),1)
            self.assertEqual(set(db.rows),{User,SubscriptionPlan,PaymentCheckout,Subscription,
                CreditTransaction,PaidCreditAllocation,Payment,__import__('app.models.payment_preparation',fromlist=['PaymentWebhookEvent']).PaymentWebhookEvent})

    def test_role_change_sends_payment_to_review_without_grant(self):
        p=role_purchase('owner','starter'); db=MemorySession()
        db.add(PaymentCheckout(**{k:v for k,v in vars(p).items() if k!='role'}))
        db.add(User(id=7,name='Changed',email='changed@example.test',role='user',is_verified=True))
        db.add(SubscriptionPlan(id=12,user_role='owner',code='starter'))
        proof=verify_paid(provider(role_objects(p)),p,'cs_test_mock')
        repo=PaymentRepository(db)
        self.assertEqual(repo.apply_event(event(),b'a'*32,proof)['outcome'],'review')
        self.assertNotIn(CreditTransaction,db.rows)

    @patch('app.core.stripe_test.RELEASE_VERIFIED', False)
    @patch('app.core.stripe_test.STRIPE_TEST_ENABLED', False)
    def test_release_and_environment_cannot_enable_payments(self):
        self.assertFalse(stripe_test.RELEASE_VERIFIED)
        self.assertFalse(stripe_test.STRIPE_TEST_ENABLED)
        with patch.dict('os.environ',{'STRIPE_TEST_ENABLED':'true'}):
            self.assertFalse(stripe_test.configuration().enabled)
            with self.assertRaises(HTTPException): stripe_test.require_release()

    def test_request_rejects_client_price_and_foreign_role_plans(self):
        from pydantic import ValidationError
        for request in [lambda: UserCheckoutRequest(plan_code='starter',idempotency_key='a'*32,price_id=PRICE_IDS[('owner','starter')]),
                        lambda: OwnerCheckoutRequest(plan_code='pro',idempotency_key='a'*32)]:
            with self.assertRaises(ValidationError): request()
        for role,code in [('user','growth'),('owner','pro'),('admin','starter')]:
            with self.assertRaises(HTTPException): paid_plan(role,code)

    def test_expired_normal_subscription_does_not_reset_free_allowance(self):
        from app.services.user_payment_subscription import status
        user=SimpleNamespace(id=7,role='user'); db=Mock()
        db.scalars.return_value=[SimpleNamespace(end_date=NOW-timedelta(days=1))]
        with patch('app.services.user_payment_subscription.require_release'),patch('app.services.user_payment_subscription.lock_profile',return_value=user),patch('app.services.user_payment_subscription.clock',return_value=NOW):
            result=status(db,user)
        self.assertEqual(result['plan'],'free')
        self.assertFalse(result['paid_generation_available'])
        db.add.assert_not_called(); db.commit.assert_not_called(); db.rollback.assert_called_once()

    def test_normal_checkout_skips_owner_onboarding_and_checks_catalogue(self):
        db=MemorySession(); user=User(id=7,role='user',name='User',email='mock@example.test'); db.add(user)
        db.add(SubscriptionPlan(id=12,user_role='user',code='starter',name='Starter',price=490,
            monthly_credits=40,currency='LKR',is_active=True,max_projects=None,max_share_links=None))
        repo=PaymentRepository(db)
        with patch('app.repositories.payment_repository.lock_profile',return_value=user),patch('app.repositories.payment_repository.find_owner_profile') as studio,patch('app.repositories.payment_repository.clock',return_value=NOW):
            result=repo.reserve_purchase(user,UserCheckoutRequest(plan_code='starter',idempotency_key='a'*32))
            self.assertEqual((result.role,result.amount_minor,result.credits),('user',49000,40))
            studio.assert_not_called()
        self.assertNotIn(CreditTransaction,db.rows)

if __name__=='__main__': unittest.main()
