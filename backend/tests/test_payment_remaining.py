"""All-role reversal regression and approved Price IDs; no DB or live requests."""
import unittest
from app.core.stripe_prices import PRICE_IDS, paid_plan
from app.models.subscription_plan import SubscriptionPlan
from app.models.subscription import Subscription
from app.models.credit_transaction import CreditTransaction
from app.models.payment_preparation import PaidCreditAllocation
from app.models.payment import Payment
import test_manual_stripe_renewal as renewal
from test_stripe_preparation import NOW

class RemainingPaymentTests(unittest.TestCase):
    def test_exact_approved_price_ids(self):
        self.assertEqual(PRICE_IDS,{
            ('user','starter'):'price_1UbwQY0AIz9Esgr8Km6SmqC1',
            ('user','pro'):'price_1UbwUl0AIz9Esgr845GBoeQF',
            ('owner','starter'):'price_1UbwaP0AIz9Esgr8CPe04N39',
            ('owner','growth'):'price_1Ubwbk0AIz9Esgr85sCh27ZK',
            ('owner','unlimited'):'price_1Ubwd20AIz9Esgr8vvcyskSz',
        })

    def test_refund_dispute_duplicate_and_late_success_all_roles(self):
        helper=renewal.ManualRenewalTests()
        for role,code,credits in renewal.PLANS:
            for reversal in ('partial_refund','refund','dispute'):
                with self.subTest(role=role,plan=code,reversal=reversal):
                    db,user,repo=helper.setup_account(role,code)
                    db.add(SubscriptionPlan(id=10,code='basic',user_role='owner'))
                    p=helper.reserve(repo,user,code,NOW,'a')
                    data,success=helper.remote_event(p,NOW,'evt_success')
                    helper.deliver(repo,data,success,NOW)
                    amount=paid_plan(role,code).amount_minor
                    if reversal=='dispute':
                        data['disputes/dp_mock'].update(charge=f'ch_{p.id}')
                        event={'id':'evt_reverse','type':'charge.dispute.created','data':{'object':{'id':'dp_mock'}},'livemode':False}
                    else:
                        data['refunds/re_mock'].update(charge=f'ch_{p.id}',amount=amount//2 if reversal=='partial_refund' else amount)
                        event={'id':'evt_reverse','type':'refund.updated','data':{'object':{'id':'re_mock'}},'livemode':False}
                    helper.deliver(repo,data,event,NOW)
                    helper.deliver(repo,data,event,NOW)
                    helper.deliver(repo,data,{**success,'id':'evt_late_success'},NOW)
                    self.assertEqual(len(db.rows[CreditTransaction]),1)
                    self.assertEqual(db.rows[CreditTransaction][0].credits_change,credits)
                    self.assertIsNotNone(db.rows[PaidCreditAllocation][0].revoked_at)
                    self.assertEqual(db.rows[Subscription][0].status,'cancelled')
                    self.assertEqual(db.rows[Payment][0].status,{'refund':'refunded','partial_refund':'partially_refunded','dispute':'disputed'}[reversal])
                    if role=='owner':self.assertEqual(db.rows[Subscription][-1].plan_kind,'basic')
                    else:self.assertEqual(len(db.rows[Subscription]),1)
                    helper.assert_free_unchanged(db)
