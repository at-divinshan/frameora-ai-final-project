"""Admin billing reads against disposable SQLite only; no provider calls."""
from datetime import timedelta
from unittest.mock import patch
import unittest
from sqlalchemy import event
from sqlalchemy.orm import Session
import test_owner_subscriptions
from app.models.account_status import AccountStatus, AccountStatusAudit
from app.models.subscription import Subscription
from app.models.credit_transaction import CreditTransaction
from app.models.free_generation_allowance import FreeGenerationAllowance
from app.models.payment import Payment


class AdminBillingTests(unittest.TestCase):
    auth = test_owner_subscriptions.OwnerSubscriptionTests.auth
    tearDown = test_owner_subscriptions.OwnerSubscriptionTests.tearDown

    def setUp(self):
        test_owner_subscriptions.OwnerSubscriptionTests.setUp(self)
        for model in (AccountStatus, AccountStatusAudit, Payment, FreeGenerationAllowance):
            model.__table__.create(self.engine)
        self.admin = self.auth(3)
        with Session(self.engine) as db:
            db.add(Subscription(id=1,user_id=2,plan_id=1,plan_kind='basic',status='active',
                                start_date=self.now,activation_key=b'isolated'))
            db.flush()
            for index,(kind,amount) in enumerate((('grant',10),('spend',-4),('refund',2))):
                db.add(CreditTransaction(user_id=2,subscription_id=1,transaction_type=kind,credits_change=amount,
                    period_start=self.now,period_end=self.now.replace(month=2),created_at=self.now,
                    operation_key=str(index).encode(),request_hash=b'x'*32))
            for index in range(22):
                db.add(Payment(user_id=2,subscription_id=1,amount='490.25',status='recorded',created_at=self.now))
            # Even a bad legacy cross-account subscription link must not reveal another user's plan.
            db.add(Payment(user_id=1,subscription_id=1,amount='12.00',status='recorded',created_at=self.now))
            db.commit()

    def test_admin_only_allowlist_real_ledger_and_paginated_payments(self):
        for headers,code in (({},401),(self.auth(1),403),(self.auth(2),403)):
            self.assertEqual(self.client.get('/admin/users/2',headers=headers).status_code,code)
        def no_writes(conn,cursor,statement,parameters,context,many):
            self.assertNotIn(statement.lstrip().split()[0].upper(),('INSERT','UPDATE','DELETE','ALTER','CREATE'))
        event.listen(self.engine,'before_cursor_execute',no_writes)
        try:
            response=self.client.get('/admin/users/2',headers=self.admin)
            self.assertEqual(response.status_code,200,response.text)
            data=response.json()
            self.assertEqual([data['subscription'][k] for k in ('plan','allocated','used','remaining')],['Free Basic',10,2,8])
            self.assertEqual(data['payments']['total'],22)
            self.assertEqual(len(data['payments']['items']),20)
            payment=data['payments']['items'][0]
            self.assertEqual(payment['amount'],'490.25')
            self.assertEqual(payment['plan'],'Free Basic')
            for key in ('currency','method','transaction_id'):self.assertIsNone(payment[key])
            second=self.client.get('/admin/users/2?payment_page=2',headers=self.admin).json()
            self.assertEqual(len(second['payments']['items']),2)
            self.assertTrue({p['record_id'] for p in data['payments']['items']}.isdisjoint(p['record_id'] for p in second['payments']['items']))
            self.assertEqual(self.client.get('/admin/users/2?payment_page=0',headers=self.admin).status_code,422)
            for secret in ('password_hash','google_sub','auth_version','activation_key','operation_key','request_hash'):
                self.assertNotIn(secret,response.text)
        finally:event.remove(self.engine,'before_cursor_execute',no_writes)

    def test_normal_user_allowance_not_monthly_credits_and_owned_payment_links(self):
        data=self.client.get('/admin/users/1',headers=self.admin).json()
        self.assertEqual(data['subscription']['allowance_status'],'available')
        self.assertIsNone(data['subscription']['allocated'])
        self.assertIsNone(data['subscription']['plan'])
        self.assertEqual(len(data['payments']['items']),1)
        self.assertIsNone(data['payments']['items'][0]['plan'])
        with Session(self.engine) as db:
            db.add(FreeGenerationAllowance(user_id=1,state='reserved',reservation_key=b'x'*32,
                                          generation_id=1,reserved_at=self.now))
            db.commit()
        self.assertEqual(self.client.get('/admin/users/1',headers=self.admin).json()['subscription']['allowance_status'],'in_progress')
        with Session(self.engine) as db:
            row=db.get(FreeGenerationAllowance,1);row.state='consumed';row.reservation_key=None;row.consumed_at=self.now
            db.commit()
        self.assertEqual(self.client.get('/admin/users/1',headers=self.admin).json()['subscription']['allowance_status'],'used')

    def test_missing_empty_and_unrecorded_renewals(self):
        with Session(self.engine) as db:
            db.query(Payment).delete();db.commit()
        data=self.client.get('/admin/users/2',headers=self.admin).json()
        self.assertTrue(data['payments']['available']);self.assertEqual(data['payments']['total'],0)
        self.now=self.now.replace(month=2)
        data=self.client.get('/admin/users/2',headers=self.admin).json()
        self.assertIsNone(data['subscription']['remaining'])
        self.assertIn('No recorded allocation',data['subscription']['note'])
        with Session(self.engine) as db:
            sub=db.get(Subscription,1);sub.end_date=self.now-timedelta(days=1);db.commit()
        data=self.client.get('/admin/users/2',headers=self.admin).json()
        self.assertEqual(data['subscription']['status'],'expired')
        self.assertIsNone(data['subscription']['remaining'])
        Payment.__table__.drop(self.engine)
        self.assertFalse(self.client.get('/admin/users/2',headers=self.admin).json()['payments']['available'])
