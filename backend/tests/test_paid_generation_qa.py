"""Paid batch and Owner limit QA using mock sessions only."""
import unittest
from contextlib import ExitStack
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from fastapi import HTTPException
import app.main
from app.models.user import User
from app.models.subscription import Subscription
from app.models.credit_transaction import CreditTransaction
from app.models.ai_generation import AIGeneration
from app.models.media_asset import MediaAsset
from app.services import ai_service, user_paid_generation, paid_credit_service
from app.services import owner_generation_service as owner, owner_entitlement_service as entitlements
from app.core.owner_plans import BY_CODE, limit_reached
from test_manual_stripe_renewal import RenewalSession
from test_stripe_preparation import NOW

class PaidGenerationQATests(unittest.TestCase):
    def test_successful_normal_batch_and_retry_deduct_exactly_four(self):
        for code,credits in [('starter',40),('pro',100)]:
            with self.subTest(plan=code),ExitStack() as stack:
                db=RenewalSession();user=User(id=7,role='user')
                sub=Subscription(id=8,user_id=7,plan_id=12,plan_kind=code,status='active',start_date=NOW,end_date=NOW+timedelta(days=30))
                db.add(user);db.add(sub)
                db.add(CreditTransaction(user_id=7,subscription_id=8,credits_change=credits,transaction_type='grant',period_start=sub.start_date,period_end=sub.end_date))
                allocation=NS(credits=credits,period_start=sub.start_date,period_end=sub.end_date)
                for target,value in [(user_paid_generation,'lock_profile'),(ai_service,'lock_profile')]:
                    stack.enter_context(patch.object(target,value,return_value=user))
                stack.enter_context(patch.object(user_paid_generation,'clock',return_value=NOW))
                stack.enter_context(patch.object(paid_credit_service,'proof',return_value=allocation))
                stack.enter_context(patch.object(ai_service.plan_repository,'find_for_user',return_value=NS(id=1)))
                stack.enter_context(patch.object(ai_service,'build_image_prompt',return_value='fixed prompt'))
                stack.enter_context(patch.object(ai_service,'planned_shots',return_value=[{}]*4))
                stack.enter_context(patch.object(ai_service,'generation_view',side_effect=lambda db,g:{'id':g.id,'status':g.status}))
                stack.enter_context(patch.object(ai_service.provider,'require_reference_support'))
                stack.enter_context(patch.object(ai_service.provider,'require_configured'))
                generate=stack.enter_context(patch.object(ai_service.provider,'generate_images',return_value=[b'a',b'b',b'c',b'd']))
                stack.enter_context(patch.object(ai_service.storage,'write_image',side_effect=['a','b','c','d']))
                free=stack.enter_context(patch.object(ai_service.allowance,'reserve_free_request',side_effect=AssertionError('Never reset free history')))
                args=dict(plan_id=1,description='',reference=None,idempotency_key='stable-request-key')
                first=ai_service.generate(db,user,**args);second=ai_service.generate(db,user,**args)
                self.assertEqual(first,second);self.assertEqual(first['status'],'completed')
                self.assertEqual(len(db.rows[MediaAsset]),4)
                self.assertEqual([r.credits_change for r in db.rows[CreditTransaction]],[credits,-4])
                self.assertEqual(paid_credit_service.balance(db,sub,NOW)[0],credits-4)
                generate.assert_called_once();free.assert_not_called()

    def test_owner_verified_entitlements_and_limits_for_each_paid_plan(self):
        for code in ('starter','growth','unlimited'):
            with self.subTest(plan=code),ExitStack() as stack:
                plan=BY_CODE[code];user=NS(id=7,role='owner');sub=NS(id=8,plan_kind=code,plan_id=12,status='active',start_date=NOW,end_date=NOW+timedelta(days=30))
                db=Mock();db.scalars.return_value=[sub];db.scalar.return_value=1
                stack.enter_context(patch.object(entitlements,'lock_profile',return_value=user))
                stack.enter_context(patch.object(entitlements.subscriptions,'require_schema'))
                stack.enter_context(patch.object(entitlements.subscriptions,'plans',return_value={code:NS(id=12)}))
                stack.enter_context(patch.object(entitlements,'find_owner_profile',return_value=NS(onboarding_status='completed')))
                balance=stack.enter_context(patch.object(paid_credit_service,'balance',return_value=(plan.credits,NOW,sub.end_date)))
                _,state=entitlements.resolve_locked(db,user,now=NOW)
                self.assertEqual((state['max_projects'],state['max_share_links']),(plan.max_projects,plan.max_share_links))
                self.assertEqual(state['batch_cost'],2);self.assertTrue(state['generation_allowed'])
                balance.assert_called_once();db.add.assert_not_called()
                for limit in (state['max_projects'],state['max_share_links']):
                    if limit is None:self.assertFalse(limit_reached(1000000,limit))
                    else:self.assertFalse(limit_reached(limit-1,limit));self.assertTrue(limit_reached(limit,limit))
                balance.side_effect=HTTPException(503,'Unverified')
                with self.assertRaises(HTTPException):entitlements.resolve_locked(db,user,now=NOW)

    def test_owner_reservation_retry_and_original_period_refund(self):
        for code in ('starter','growth','unlimited'):
            with self.subTest(plan=code),ExitStack() as stack:
                db=Mock();db.scalar.return_value=None;db.scalars.return_value=[]
                db.add.side_effect=lambda row:setattr(row,'id',9) if isinstance(row,AIGeneration) else None
                user=NS(id=7,role='owner');sub=NS(id=8,user_id=7)
                stack.enter_context(patch.object(owner,'_lock_owner'))
                stack.enter_context(patch.object(owner.subscriptions,'clock',return_value=NOW))
                stack.enter_context(patch.object(owner.plan_repository,'find_for_user',return_value=NS(id=1)))
                stack.enter_context(patch.object(owner,'build_owner_image_prompt',return_value='prompt'))
                stack.enter_context(patch.object(owner,'planned_owner_shots',return_value=[{},{}]))
                stack.enter_context(patch.object(owner.provider,'require_configured'))
                stack.enter_context(patch.object(entitlements,'resolve_locked',return_value=(sub,dict(generation_allowed=True,period_start=NOW,period_end=NOW+timedelta(days=30)))))
                owner._reserve(db,user,1,'',None,'stable-key')
                generation=db.add.call_args_list[0].args[0];debit=db.add.call_args_list[1].args[0]
                self.assertEqual((debit.credits_change,debit.subscription_id),(-2,8))
                db.reset_mock();db.scalar.return_value=debit
                with patch.object(owner,'_owned',return_value=(generation,debit)):
                    self.assertEqual(owner._reserve(db,user,1,'',None,'stable-key')[0],9)
                db.add.assert_not_called()
                db.scalar.return_value=None
                owner._refund_locked(db,generation,debit,NOW+timedelta(days=31))
                owner._refund_locked(db,generation,debit,NOW+timedelta(days=31))
                db.add.assert_called_once();refund=db.add.call_args.args[0]
                self.assertEqual((refund.credits_change,refund.subscription_id,refund.period_end),(2,8,debit.period_end))
