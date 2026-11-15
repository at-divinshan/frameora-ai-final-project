"""No SQL engines or database writes. Stripe uses httpx.MockTransport only."""
import copy
import hashlib
import hmac
import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
import httpx
from fastapi import HTTPException
from app.core.stripe_test import StripeTestConfig
from app.core.stripe_prices import checkout_metadata, PRICE_IDS
from app.services.stripe_test_provider import StripeTestProvider, verify_event
from app.services.payment_processing import verify_paid, process_event, start_checkout, VerifiedPayment
from app.services import payment_service, credit_service
from app.repositories.payment_repository import PaymentRepository
from app.models.payment_preparation import PaymentCheckout, PaymentWebhookEvent, PaidCreditAllocation
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.credit_transaction import CreditTransaction
from app.models.user import User
from app.models.photography_plan import PhotographyPlan
from app.models.subscription_plan import SubscriptionPlan

SECRET='whsec_mock_only'
NOW=datetime(2026,11,14,8)


def purchase():
    return SimpleNamespace(role='owner',id=1,user_id=7,plan_id=12,plan_code='starter',amount_minor=150000,
        currency='lkr',credits=100,request_key=b'a'*32,request_hash=b'b'*32,
        created_at=NOW-timedelta(minutes=5),expires_at=NOW+timedelta(minutes=55),
        provider_session_id='cs_test_mock',provider_payment_id=None,payment_id=None,
        state='open',livemode=False,verified_at=None,revoked_at=None)

def objects(p=None):
    p=p or purchase()
    metadata=checkout_metadata(p)
    price={'id':PRICE_IDS[('owner','starter')],'livemode':False,'active':True,'currency':'lkr',
           'unit_amount':150000,'type':'one_time','recurring':None,'billing_scheme':'per_unit'}
    return {
        'prices/'+price['id']:price,
        'checkout/sessions/cs_test_mock/line_items':{'has_more':False,'data':[{'quantity':1,'amount_subtotal':150000,'amount_total':150000,'currency':'lkr','price':price}]},
        'checkout/sessions/cs_test_mock':{'id':'cs_test_mock','livemode':False,'metadata':metadata,
            'mode':'payment','status':'complete','payment_status':'paid','client_reference_id':'1',
            'amount_total':150000,'currency':'lkr','payment_intent':'pi_mock'},
        'payment_intents/pi_mock':{'id':'pi_mock','livemode':False,'metadata':metadata,
            'status':'succeeded','amount':150000,'amount_received':150000,'currency':'lkr','latest_charge':'ch_mock'},
        'charges/ch_mock':{'id':'ch_mock','livemode':False,'payment_intent':'pi_mock','paid':True,
            'captured':True,'amount':150000,'currency':'lkr','amount_refunded':0,'disputed':False,
            'created':int(NOW.replace(tzinfo=__import__('datetime').timezone.utc).timestamp())},
        'refunds/re_mock':{'id':'re_mock','charge':'ch_mock','status':'succeeded','amount':150000,'currency':'lkr'},
        'disputes/dp_mock':{'id':'dp_mock','livemode':False,'charge':'ch_mock','status':'needs_response','currency':'lkr'},
    }

def provider(data=None, seen=None):
    data=data or objects()
    def respond(req):
        if seen is not None: seen.append(req)
        return httpx.Response(200,json=data[req.url.path.removeprefix('/v1/')])
    return StripeTestProvider(StripeTestConfig('sk_test_mock','whsec_mock','http://localhost:5173'),httpx.MockTransport(respond))

def event(kind='checkout.session.completed',identifier='evt_mock'):
    obj={'id':'cs_test_mock','metadata':{'checkout_id':'1'}}
    if kind.startswith('refund.'): obj={'id':'re_mock'}
    if kind.startswith('charge.dispute.'): obj={'id':'dp_mock'}
    return {'id':identifier,'livemode':False,'type':kind,'data':{'object':obj}}

class MemorySession:
    """Small transaction spy evaluating only the repository's selected entities.
    It executes no SQL and has no connection/engine.
    """
    def __init__(self):
        self.rows={}; self.commits=0; self.rollbacks=0; self.fail_commit=False
    def add(self,row):
        table=self.rows.setdefault(type(row),[])
        if getattr(row,'id',None) is None: row.id=len(table)+1
        table.append(row)
    def flush(self): pass
    def commit(self):
        if self.fail_commit: raise __import__('sqlalchemy').exc.SQLAlchemyError('mock failure')
        self.commits+=1
    def rollback(self): self.rollbacks+=1
    def get(self,kind,identifier,**kwargs):
        return next((r for r in self.rows.get(kind,[]) if r.id==identifier),None)
    def _matching(self,statement):
        kind=statement.column_descriptions[0]['entity']
        params=statement.compile().params
        rows=self.rows.get(kind,[])
        for name,value in params.items():
            field=name.rsplit('_',1)[0]
            if hasattr(kind,field):
                rows=[r for r in rows if getattr(r,field)==value]
        return rows
    def scalar(self,statement): return next(iter(self._matching(statement)),None)
    def scalars(self,statement): return self._matching(statement)

class StripePreparationTests(unittest.TestCase):
    def test_signature_and_replay_window(self):
        raw=json.dumps(event()).encode()
        digest=hmac.new(SECRET.encode(),b'1000.'+raw,hashlib.sha256).hexdigest()
        self.assertEqual(verify_event(raw,'t=1000,v1=wrong,v1='+digest,SECRET,now=1001)['id'],'evt_mock')
        for payload,signature,now in [(raw+b' ',f't=1000,v1={digest}',1000),(raw,f't=1000,v1={digest}',1301),
            (raw,f't=1000,v1={digest}',699),(raw,'t=1000,v1=bad',1000)]:
            with self.assertRaises(HTTPException): verify_event(payload,signature,SECRET,now=now)
        live=json.dumps({**event(),'livemode':True}).encode()
        sig=hmac.new(SECRET.encode(),b'1000.'+live,hashlib.sha256).hexdigest()
        with self.assertRaises(HTTPException): verify_event(live,'t=1000,v1='+sig,SECRET,now=1000)
        with self.assertRaises(HTTPException): verify_event(b'x'*262145,'',SECRET,now=1000)

    def test_test_only_config_and_safe_provider_urls(self):
        for key,origin in [('sk_live_forbidden','https://example.test'),('sk_test_mock','http://evil.test'),('sk_test_mock','https://user:pass@example.test')]:
            with self.assertRaises(HTTPException): StripeTestConfig(key,SECRET,origin).validate()
        with self.assertRaises(HTTPException): provider().retrieve('charges','../../secrets')

    def test_checkout_uses_one_time_mode_and_server_values(self):
        p=purchase(); p.provider_session_id=None
        returned={**objects()['checkout/sessions/cs_test_mock'],'status':'open','url':'https://checkout.stripe.com/c/pay/mock'}
        seen=[]; remote=provider({**objects(),'checkout/sessions':returned},seen)
        session=remote.create_checkout(p)
        body=seen[-1].content.decode()
        self.assertIn('mode=payment',body); self.assertNotIn('recurring',body)
        self.assertIn(PRICE_IDS[('owner','starter')],body); self.assertNotIn('price_data',body); self.assertIn('payment_intent_data',body)
        self.assertEqual(seen[-1].headers['idempotency-key'],'frameora:'+p.request_key.hex())
        self.assertEqual(session['id'],'cs_test_mock')

    def test_independent_retrieval_and_mismatch_rejection(self):
        seen=[]; verified=verify_paid(provider(seen=seen),purchase(),'cs_test_mock')
        self.assertEqual(len(seen),4); self.assertEqual(verified.amount_minor,150000)
        mutations=[('checkout/sessions/cs_test_mock','payment_status','unpaid'),
            ('checkout/sessions/cs_test_mock','amount_total',1),('checkout/sessions/cs_test_mock','currency','usd'),
            ('payment_intents/pi_mock','amount_received',0),('payment_intents/pi_mock','livemode',True),
            ('payment_intents/pi_mock','metadata',{'user_id':'8'}),('charges/ch_mock','payment_intent','pi_other')]
        for path,field,value in mutations:
            data=objects(); data[path][field]=value
            with self.assertRaises(HTTPException): verify_paid(provider(data),purchase(),'cs_test_mock')

    def test_refund_and_dispute_independent_verification(self):
        for kind in ['refund.created','refund.updated','charge.dispute.created','charge.dispute.closed']:
            store=Mock(); store.get_purchase.return_value=purchase(); store.apply_event.return_value={'received':True}
            e=event(kind)
            process_event(e,json.dumps(e).encode(),store,provider())
            proof=store.apply_event.call_args.args[2]
            self.assertTrue(proof.reversal); self.assertEqual(proof.payment_intent_id,'pi_mock')
        data=objects(); data['refunds/re_mock']['status']='failed'
        store=Mock(); store.get_purchase.return_value=purchase()
        process_event(event('refund.updated'),b'raw',store,provider(data))
        store.apply_event.assert_not_called()

    @patch('app.core.stripe_test.RELEASE_VERIFIED', False)
    @patch('app.core.stripe_test.STRIPE_TEST_ENABLED', False)
    def test_release_gate_and_unverified_paid_balance(self):
        db=Mock(); sub=SimpleNamespace(plan_kind='starter')
        with self.assertRaises(HTTPException) as exc: credit_service.balance(db,sub,NOW,grant=True)
        self.assertEqual(exc.exception.status_code,503)
        db.add.assert_not_called(); db.scalars.assert_not_called()
        with self.assertRaises(HTTPException): payment_service.receive_webhook(b'{}','',db)
        db.connection.assert_not_called()

    def repository(self):
        db=MemorySession()
        p=PaymentCheckout(**{k:v for k,v in vars(purchase()).items() if k!='role'}); db.add(p)
        db.add(User(id=7,name='Owner',email='mock@example.test',role='owner',is_verified=True))
        db.add(SubscriptionPlan(id=12,code='starter',name='Starter',user_role='owner',is_active=True,
            monthly_credits=100,price=1500,currency='LKR',max_projects=10,max_share_links=20))
        db.add(SubscriptionPlan(id=10,code='basic',name='Free Basic',user_role='owner',is_active=True,
            monthly_credits=10,price=0,currency='LKR',max_projects=2,max_share_links=3))
        repo=PaymentRepository(db)
        return repo,db,p

    def test_atomic_fulfillment_duplicate_events_and_payment_dedup(self):
        repo,db,p=self.repository()
        verified=verify_paid(provider(),purchase(),'cs_test_mock')
        e=event(); raw=json.dumps(e).encode()
        with patch('app.core.account_state.require_active'), patch('app.repositories.payment_repository.clock',return_value=NOW):
            result=repo.apply_event(e,hashlib.sha256(raw).digest(),verified)
            self.assertEqual(result['outcome'],'fulfilled')
            repo.apply_event(e,hashlib.sha256(raw).digest(),verified)
            e2=event(identifier='evt_other'); repo.apply_event(e2,b'c'*32,verified)
        self.assertEqual(len(db.rows[Subscription]),1)
        self.assertEqual(len(db.rows[CreditTransaction]),1)
        self.assertEqual(len(db.rows[Payment]),1)
        self.assertEqual(len(db.rows[PaidCreditAllocation]),1)
        self.assertEqual(len(db.rows[PaymentWebhookEvent]),2)
        self.assertEqual(db.rows[Subscription][0].end_date,datetime(2026,12,14,8))
        self.assertEqual(db.commits,3)

    def test_refund_cancels_only_linked_period_and_never_regrants(self):
        repo,db,p=self.repository(); verified=verify_paid(provider(),purchase(),'cs_test_mock')
        with patch('app.core.account_state.require_active'), patch('app.repositories.payment_repository.clock',return_value=NOW):
            repo.apply_event(event(),b'a'*32,verified)
            reversed_proof=VerifiedPayment(1,'cs_test_mock','pi_mock',150000,'lkr',NOW,True,'refund')
            repo.apply_event(event('refund.created','evt_refund'),b'b'*32,reversed_proof)
            repo.apply_event(event(identifier='evt_late'),b'c'*32,verified)
        self.assertEqual(p.state,'revoked')
        self.assertEqual(db.rows[PaidCreditAllocation][0].revoked_at,NOW)
        self.assertEqual(db.rows[Subscription][0].status,'cancelled')
        self.assertEqual(db.rows[Subscription][1].plan_kind,'basic')
        self.assertEqual(len(db.rows[CreditTransaction]),1)

    def test_refund_before_success_cannot_activate(self):
        repo,db,p=self.repository()
        proof=VerifiedPayment(1,'cs_test_mock','pi_mock',150000,'lkr',NOW,True,'dispute')
        repo.apply_event(event('charge.dispute.created'),b'a'*32,proof)
        repo.apply_event(event(identifier='evt_late'),b'b'*32,verify_paid(provider(),purchase(),'cs_test_mock'))
        self.assertFalse(db.rows.get(Subscription)); self.assertFalse(db.rows.get(CreditTransaction))

    def test_uncertain_commit_returns_retryable_error(self):
        repo,db,p=self.repository(); db.fail_commit=True
        with patch('app.core.account_state.require_active'), patch('app.repositories.payment_repository.clock',return_value=NOW):
            with self.assertRaises(HTTPException) as exc:
                repo.apply_event(event(),b'a'*32,verify_paid(provider(),purchase(),'cs_test_mock'))
        self.assertEqual(exc.exception.status_code,503); self.assertGreater(db.rollbacks,0)

    def test_missing_schema_is_rejected_without_writes(self):
        from app.services.payment_schema import require_payment_schema
        inspector=Mock(); inspector.dialect.name='mysql'; inspector.has_table.return_value=False
        db=Mock()
        with patch('app.services.payment_schema.inspect',return_value=inspector):
            with self.assertRaises(HTTPException) as exc: require_payment_schema(db)
        self.assertEqual(exc.exception.status_code,503)
        db.add.assert_not_called(); db.commit.assert_not_called()

    def test_paid_proof_requires_receipt_grant_and_nonrevoked_period(self):
        from app.services.paid_credit_service import proof, balance
        from decimal import Decimal
        sub=SimpleNamespace(id=3,user_id=7,plan_id=12,plan_kind='starter',status='active',
            start_date=NOW,end_date=NOW+timedelta(days=30))
        allocation=SimpleNamespace(period_start=sub.start_date,period_end=sub.end_date,credits=100,revoked_at=None)
        checkout=purchase(); checkout.state='fulfilled'; checkout.verified_at=NOW; checkout.provider_payment_id='pi_mock'
        payment=SimpleNamespace(status='succeeded',user_id=7,subscription_id=3,amount=Decimal('1500'))
        grant=SimpleNamespace(credits_change=100,transaction_type='grant',user_id=7,subscription_id=3,period_start=sub.start_date,period_end=sub.end_date)
        db=Mock(); db.execute.return_value.one_or_none.return_value=(allocation,checkout,payment,grant)
        db.get.side_effect=lambda model,identifier: SimpleNamespace(role='owner') if model is User else SimpleNamespace(user_role='owner')
        db.scalars.return_value=[grant,SimpleNamespace(credits_change=-2,transaction_type='spend')]
        with patch('app.services.paid_credit_service.require_release'), patch('app.services.payment_schema.require_payment_schema'):
            self.assertEqual(balance(db,sub,NOW)[0],98)
            for target,field,value in [(checkout,'verified_at',None),(checkout,'state','open'),(payment,'status','refunded'),(allocation,'revoked_at',NOW),(grant,'credits_change',101),(payment,'amount',Decimal('1'))]:
                old=getattr(target,field); setattr(target,field,value)
                with self.assertRaises(HTTPException): proof(db,sub,NOW)
                setattr(target,field,old)
            with self.assertRaises(HTTPException): proof(db,sub,sub.end_date)
            self.assertIs(proof(db,sub,sub.end_date,settlement=True),allocation)
        db.add.assert_not_called(); db.commit.assert_not_called()

    def test_checkout_reservation_replay_and_conflict(self):
        from app.schemas.payment import OwnerCheckoutRequest
        repo,db,p=self.repository(); db.rows[PaymentCheckout]=[]
        owner=db.get(User,7)
        request=OwnerCheckoutRequest(plan_code='starter',idempotency_key='a'*32)
        with patch('app.repositories.payment_repository.lock_profile',return_value=owner), patch('app.repositories.payment_repository.find_owner_profile',return_value=SimpleNamespace(onboarding_status='completed')), patch('app.repositories.payment_repository.clock',return_value=NOW):
            one=repo.reserve_purchase(owner,request); two=repo.reserve_purchase(owner,request)
            self.assertEqual(one.id,two.id); self.assertEqual(len(db.rows[PaymentCheckout]),1)
            with self.assertRaises(HTTPException) as exc:
                repo.reserve_purchase(owner,OwnerCheckoutRequest(plan_code='growth',idempotency_key='a'*32))
            self.assertEqual(exc.exception.status_code,409)
        self.assertFalse(db.rows.get(CreditTransaction)); self.assertFalse(db.rows.get(Payment))

    def test_wrong_event_hash_and_disabled_account_do_not_grant(self):
        repo,db,p=self.repository(); verified=verify_paid(provider(),purchase(),'cs_test_mock')
        with patch('app.core.account_state.require_active',side_effect=HTTPException(401,'inactive')), patch('app.repositories.payment_repository.clock',return_value=NOW):
            self.assertEqual(repo.apply_event(event(),b'a'*32,verified)['outcome'],'review')
            with self.assertRaises(HTTPException): repo.apply_event(event(),b'b'*32,verified)
        self.assertFalse(db.rows.get(CreditTransaction)); self.assertFalse(db.rows.get(Subscription))

    @patch('app.core.stripe_test.RELEASE_VERIFIED', False)
    @patch('app.core.stripe_test.STRIPE_TEST_ENABLED', False)
    def test_http_routes_are_disabled_and_owner_only_without_database_access(self):
        import asyncio
        from app.main import app
        from app.core.dependencies import get_current_user
        from app.database.connection import get_db
        identity=SimpleNamespace(id=7,role='owner')
        db=Mock()
        saved=dict(app.dependency_overrides)
        app.dependency_overrides[get_current_user]=lambda: identity
        app.dependency_overrides[get_db]=lambda: db
        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.get('/owner/payments/readiness')
                self.assertEqual(response.status_code,200)
                self.assertFalse(response.json()['paid_activation_available'])
                response=await client.post('/owner/payments/checkout',json={'plan_code':'starter','idempotency_key':'a'*32})
                self.assertEqual(response.status_code,503)
                response=await client.post('/owner/payments/checkout',json={'plan_code':'starter','idempotency_key':'a'*32,'amount':1})
                self.assertEqual(response.status_code,422)
                response=await client.post('/payments/stripe/webhook',content=b'{}')
                self.assertEqual(response.status_code,503)
                for role in ['admin','user']:
                    identity.role=role
                    response=await client.get('/owner/payments/readiness')
                    self.assertEqual(response.status_code,403)
                    response=await client.post('/owner/payments/checkout',json={'plan_code':'starter','idempotency_key':'a'*32})
                    self.assertEqual(response.status_code,403)
                identity.role='user'
                response=await client.get('/user/payments/readiness')
                self.assertEqual(response.status_code,200)
                response=await client.post('/user/payments/checkout',json={'plan_code':'pro','idempotency_key':'a'*32})
                self.assertEqual(response.status_code,503)
                response=await client.post('/user/payments/checkout',json={'plan_code':'growth','idempotency_key':'a'*32})
                self.assertEqual(response.status_code,422)
                response=await client.get('/user/payments/subscription')
                self.assertEqual(response.status_code,503)
                for role in ['owner','admin']:
                    identity.role=role
                    response=await client.post('/user/payments/checkout',json={'plan_code':'pro','idempotency_key':'a'*32})
                    self.assertEqual(response.status_code,403)
        try:
            with patch('sqlalchemy.engine.Engine.connect',side_effect=AssertionError('No database allowed')):
                asyncio.run(exercise())
        finally:
            app.dependency_overrides.clear(); app.dependency_overrides.update(saved)
        db.add.assert_not_called(); db.commit.assert_not_called(); db.connection.assert_not_called()

    def test_expired_paid_period_falls_back_without_extending_it(self):
        from app.services.subscription_service import resolve_effective
        sub=SimpleNamespace(id=8,end_date=NOW-timedelta(days=1),status='active')
        db=Mock()
        fallback=resolve_effective(db,7,sub,{'basic':SimpleNamespace(id=10)},NOW,persist=False)
        self.assertEqual(fallback.plan_kind,'basic'); self.assertEqual(fallback.start_date,sub.end_date)
        db.add.assert_not_called()

if __name__=='__main__': unittest.main()
