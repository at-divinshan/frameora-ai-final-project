"""Admin billing projection tests with mock sessions only."""
import unittest
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from fastapi import HTTPException
import app.main
from app.services import admin_billing_service as billing, admin_users_service
from app.models.payment_preparation import PaymentCheckout
from app.models.credit_transaction import CreditTransaction
from test_stripe_preparation import NOW

class AdminPaymentVisibilityTests(unittest.TestCase):
    def test_recorded_stripe_fields_and_review_plan_are_visible_without_secrets(self):
        for role in ('user','owner'):
            with self.subTest(role=role):
                db=Mock();db.scalar.return_value=1
                payment=NS(id=1,subscription_id=None,created_at=NOW,amount='490.00',status='review')
                checkout=NS(payment_id=1,plan_id=12,provider_payment_id='pi_mock_recorded',currency='lkr')
                db.scalars.side_effect=[[payment],[checkout]]
                first,second=Mock(),Mock();first.all.return_value=[];second.all.return_value=[(12,'Starter')]
                db.execute.side_effect=[first,second]
                with patch.object(billing,'available',return_value=True):
                    result=billing.payment_details(db,NS(id=7,role=role),1)
                row=result['items'][0]
                self.assertEqual((row['transaction_id'],row['currency'],row['role'],row['plan'],row['status']),
                                 ('pi_mock_recorded','LKR',role,'Starter','review'))
                self.assertIsNone(row['method']);self.assertEqual(row['provider'],'stripe')
                self.assertEqual(set(row),{'record_id','role','subscription_id','transaction_id','date','amount','currency','method','provider','plan','status'})
                db.add.assert_not_called();db.commit.assert_not_called()
                query=db.scalars.call_args_list[-1].args[0]
                self.assertEqual(query.compile().params['user_id_1'],7)

    def test_legacy_payments_remain_visible_without_invented_gateway_fields(self):
        db=Mock();db.scalar.return_value=1
        db.scalars.return_value=[NS(id=1,subscription_id=None,created_at=NOW,amount=10,status='recorded')]
        db.execute.return_value.all.return_value=[]
        with patch.object(billing,'available',side_effect=lambda db,*models: PaymentCheckout not in models):
            row=billing.payment_details(db,NS(id=7,role='owner'),1)['items'][0]
        for name in ('transaction_id','currency','method','provider'):self.assertIsNone(row[name])

    def test_normal_paid_plans_use_verified_recorded_credits_and_keep_free_history(self):
        for code,credits in [('starter',40),('pro',100)]:
            with self.subTest(plan=code):
                db=Mock();sub=NS(id=8,plan_id=12,plan_kind=code,status='active',start_date=NOW,end_date=NOW+timedelta(days=30))
                db.scalar.side_effect=[sub,NS(name=code.title())]
                db.scalars.return_value=[NS(transaction_type='grant',credits_change=credits),NS(transaction_type='spend',credits_change=-4)]
                with patch.object(billing,'available',return_value=True),patch.object(billing.free_generation_service,'_status_for',return_value='used'), \
                     patch.object(billing.subscription_service,'clock',return_value=NOW), \
                     patch('app.services.paid_credit_service.proof') as proof:
                    result=billing.subscription_details(db,NS(id=7,role='user'))
                self.assertEqual((result['allocated'],result['used'],result['remaining'],result['allowance_status']),(credits,4,credits-4,'used'))
                proof.assert_called_once();db.add.assert_not_called();db.commit.assert_not_called()

    def test_unverified_paid_balance_stays_unavailable(self):
        db=Mock();db.scalar.side_effect=[NS(id=8,plan_id=12,plan_kind='pro',status='active',start_date=NOW,end_date=NOW+timedelta(days=30)),NS(name='Pro')]
        with patch.object(billing,'available',return_value=True),patch.object(billing.free_generation_service,'_status_for',return_value='used'), \
             patch.object(billing.subscription_service,'clock',return_value=NOW),patch('app.services.paid_credit_service.proof',side_effect=HTTPException(503,'Disabled')):
            result=billing.subscription_details(db,NS(id=7,role='user'))
        self.assertIsNone(result['remaining']);db.scalars.assert_not_called()

    def test_non_admin_cannot_read_account_billing(self):
        for role in ('owner','user'):
            db=Mock()
            with self.assertRaises(HTTPException) as error:admin_users_service.detail(db,NS(role=role),7)
            self.assertEqual(error.exception.status_code,403);db.get.assert_not_called();db.connection.assert_not_called()
