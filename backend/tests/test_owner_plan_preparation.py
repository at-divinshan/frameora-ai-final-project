"""Pure/mocked tests: no engine, SQL, provider, or database writes."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from app.core.owner_plans import BY_CODE, catalogue, limit_reached, validate_limit
from app.schemas.payment import OwnerCheckoutRequest
from app.services import payment_service, subscription_service, project_service, share_service

class OwnerPlanPreparationTests(unittest.TestCase):
    def test_catalogue(self):
        plans = {p['code']: p for p in catalogue()['plans']}
        self.assertEqual(set(plans), {'basic','trial','starter','growth','unlimited'})
        for code, price, credits, projects, links in [('basic',0,10,2,3),('trial',0,100,None,None),('starter',1500,100,10,20),('growth',2500,250,30,60),('unlimited',3500,500,None,None)]:
            p = plans[code]
            self.assertEqual((p['price'],p['credits'],p['max_projects'],p['max_share_links']), (price,credits,projects,links))
            self.assertEqual(p['activation_available'], code in ('basic','trial'))
        self.assertEqual(plans['trial']['trial_days'],14)

    def test_unlimited_and_finite_limits(self):
        self.assertFalse(limit_reached(100000, None))
        self.assertFalse(limit_reached(2,3))
        self.assertTrue(limit_reached(3,3))
        for invalid in [-1, 'unlimited', True]:
            with self.assertRaises(ValueError): validate_limit(invalid)
        projects = [SimpleNamespace(id=n) for n in range(5)]
        self.assertEqual(project_service._editable_ids(projects, None), set(range(5)))
        self.assertEqual(project_service._editable_ids(projects, 2), {0,1})

    def test_share_limit_retains_unlimited_and_downgrades(self):
        from datetime import datetime
        for limit in [None,3]:
            links=[SimpleNamespace(is_active=True, expires_at=None) for _ in range(8)]
            db=Mock(); db.execute.return_value=[(l,SimpleNamespace(deleted_at=None)) for l in links]
            with patch.object(share_service.owner_entitlement_service,'resolve_locked',return_value=(None,{'plan':'trial' if limit is None else 'basic','max_share_links':limit})):
                share_service._sync_owner_limit(db,SimpleNamespace(id=1),datetime(2026,1,1))
            self.assertEqual(sum(l.is_active for l in links),8 if limit is None else 3)

    def test_legacy_catalogue_is_not_mutated(self):
        rows=[SimpleNamespace(code=c,name=n,monthly_credits=cr,price=p,trial_days=d,currency='LKR',max_projects=pr,max_share_links=li) for c,n,cr,p,d,pr,li in [('basic','Free Basic',10,0,None,2,3),('trial','Free Trial',100,0,14,10,20),('pro','Paid Pro',500,1500,None,50,100)]]
        db=Mock(); db.scalars.return_value=rows
        self.assertIs(subscription_service.plans(db)['pro'], rows[2])
        self.assertEqual(rows[1].max_projects,10)
        db.add.assert_not_called(); db.commit.assert_not_called()
        rows[1].max_projects=rows[1].max_share_links=None
        self.assertIs(subscription_service.plans(db)['trial'],rows[1])

    def test_trial_entitlements_keep_credit_path_and_unlimited_limits(self):
        from datetime import datetime
        from app.services import owner_entitlement_service as service
        from app.schemas.owner_ai import OwnerEntitlements
        owner=SimpleNamespace(id=1,role='owner')
        sub=SimpleNamespace(id=2,user_id=1,plan_id=3,plan_kind='trial',status='active',start_date=datetime(2026,1,1),end_date=datetime(2026,1,15))
        db=Mock(); db.scalars.return_value=[sub]; db.scalar.return_value=1
        with patch.object(service,'lock_profile',return_value=owner), patch.object(service,'find_owner_profile',return_value=SimpleNamespace(onboarding_status='completed')), patch.object(service.subscriptions,'require_schema'), patch.object(service.subscriptions,'plans',return_value={'trial':SimpleNamespace(id=3)}), patch.object(service.credit_service,'balance',return_value=(73,sub.start_date,sub.end_date)) as balance:
            _, state=service.resolve_locked(db,owner,now=datetime(2026,1,2))
            self.assertIsNone(state['max_projects']); self.assertIsNone(state['max_share_links'])
            self.assertEqual(state['remaining_credits'],73)
            self.assertEqual(state['batch_cost'],2)
            OwnerEntitlements.model_validate(state)
            self.assertFalse(balance.call_args.kwargs['grant'])
        db.commit.assert_not_called(); db.add.assert_not_called()

    def test_payment_routes_require_owner(self):
        from app.routers.payments import router
        for route in router.routes:
            if route.path.startswith('/owner/'):
                dependency=route.dependant.dependencies[0].call
                for role in ['admin','user']:
                    with self.assertRaises(HTTPException) as error:
                        dependency(SimpleNamespace(role=role))
                    self.assertEqual(error.exception.status_code,403)
                owner=SimpleNamespace(role='owner')
                self.assertIs(dependency(owner),owner)

    @patch('app.core.stripe_test.RELEASE_VERIFIED', False)
    @patch('app.core.stripe_test.STRIPE_TEST_ENABLED', False)
    def test_payment_gate_and_server_owned_amounts(self):
        owner=SimpleNamespace(id=7,role='owner')
        request=OwnerCheckoutRequest(plan_code='growth',idempotency_key='a'*32)
        intent=payment_service.prepare_intent(owner,request)
        self.assertEqual((intent.user_id,intent.amount_minor,intent.credits),(7,250000,250))
        self.assertFalse(payment_service.readiness(owner)['paid_activation_available'])
        for call in [lambda: payment_service.checkout(owner,request), payment_service.receive_webhook]:
            with self.assertRaises(HTTPException) as error: call()
            self.assertEqual(error.exception.status_code,503)
        for role in ['user','admin']:
            with self.assertRaises(HTTPException) as error:
                payment_service.prepare_intent(SimpleNamespace(id=1,role=role),request)
            self.assertEqual(error.exception.status_code,422 if role=='user' else 403)
        with self.assertRaises(ValidationError):
            OwnerCheckoutRequest(plan_code='growth',idempotency_key='a'*32,amount=1)
        with self.assertRaises(ValidationError):
            OwnerCheckoutRequest(plan_code='pro',idempotency_key='a'*32)

if __name__ == '__main__': unittest.main()
