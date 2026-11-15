"""Fail-closed payment/ledger edges; mocks only, no database connections."""
import unittest
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from fastapi import HTTPException
import app.main
from app.models.user import User
from app.services import paid_credit_service
from app.services.payment_processing import verify_paid, start_checkout
from test_stripe_preparation import NOW, purchase, objects, provider

class PaymentEdgeQATests(unittest.TestCase):
    def test_unknown_or_invalid_reversal_state_cannot_activate(self):
        for field,value in [('amount_refunded',None),('amount_refunded',-1),('amount_refunded',True),
                            ('amount_refunded',150001),('disputed',None),('disputed','false')]:
            with self.subTest(field=field,value=value):
                data=objects()
                if value is None: del data['charges/ch_mock'][field]
                else: data['charges/ch_mock'][field]=value
                with self.assertRaises(HTTPException):verify_paid(provider(data),purchase(),'cs_test_mock')

    def proof_fixture(self):
        sub=NS(id=3,user_id=7,plan_id=12,plan_kind='starter',status='active',start_date=NOW,end_date=NOW+timedelta(days=30))
        allocation=NS(period_start=sub.start_date,period_end=sub.end_date,credits=100,revoked_at=None)
        checkout=purchase();checkout.state='fulfilled';checkout.verified_at=NOW;checkout.provider_payment_id='pi_mock'
        payment=NS(status='succeeded',user_id=7,subscription_id=3,amount=Decimal('1500'))
        grant=NS(credits_change=100,transaction_type='grant',user_id=7,subscription_id=3,period_start=sub.start_date,period_end=sub.end_date)
        db=Mock();db.execute.return_value.one_or_none.return_value=(allocation,checkout,payment,grant)
        db.get.side_effect=lambda model,identifier: NS(role='owner') if model is User else NS(user_role='owner',code='starter')
        return db,sub,allocation,checkout,grant

    def test_paid_proof_rejects_wrong_currency_or_unknown_mode(self):
        for field,value in [('currency','usd'),('livemode',None)]:
            db,sub,_,checkout,_=self.proof_fixture();setattr(checkout,field,value)
            with patch.object(paid_credit_service,'require_release'),patch('app.services.payment_schema.require_payment_schema'):
                with self.assertRaises(HTTPException):paid_credit_service.proof(db,sub,NOW)
            db.add.assert_not_called();db.commit.assert_not_called()

    def test_malformed_ledger_does_not_create_spendable_balance(self):
        for kind,amount in [('spend',1),('refund',-1),('unknown',-1)]:
            db,sub,allocation,_,grant=self.proof_fixture()
            db.scalars.return_value=[grant,NS(transaction_type='spend',credits_change=-10),NS(transaction_type=kind,credits_change=amount)]
            with patch.object(paid_credit_service,'proof',return_value=allocation):
                with self.assertRaises(HTTPException):paid_credit_service.balance(db,sub,NOW)

    def test_replayed_checkout_validates_session_identity_before_redirect(self):
        for field,value in [('mode','subscription'),('client_reference_id','another-user'),('amount_total',1),('currency','usd')]:
            data=objects();session=data['checkout/sessions/cs_test_mock'];session.update(status='open',url='https://checkout.stripe.com/c/pay/test')
            session[field]=value
            repo=Mock();repo.reserve_purchase.return_value=purchase()
            with self.assertRaises(HTTPException):start_checkout(repo,provider(data),NS(id=7,role='owner'),NS())
            repo.bind_session.assert_not_called()

    def test_signed_duplicate_json_keys_and_invalid_payload_types_are_rejected(self):
        import hmac,hashlib
        from app.services.stripe_test_provider import verify_event
        secret='whsec_fixture_only'
        for raw in [b'{"id":"evt_1","id":"evt_2","livemode":false,"type":"test","data":{"object":{}}}',
                    b'{"id":"evt_1","livemode":false,"type":"test","data":null}',b'[]']:
            digest=hmac.new(secret.encode(),b'1000.'+raw,hashlib.sha256).hexdigest()
            with self.assertRaises(HTTPException) as error:verify_event(raw,'t=1000,v1='+digest,secret,now=1000)
            self.assertEqual(error.exception.status_code,400)

    def test_delayed_verified_payment_keeps_original_expired_period(self):
        import test_manual_stripe_renewal as renewal
        helper=renewal.ManualRenewalTests()
        from app.models.subscription import Subscription
        from app.models.credit_transaction import CreditTransaction
        for role,code,credits in renewal.PLANS:
            with self.subTest(role=role,plan=code):
                db,user,repo=helper.setup_account(role,code)
                p=helper.reserve(repo,user,code,NOW,'a')
                data,event=helper.remote_event(p,NOW,'evt_delayed')
                helper.deliver(repo,data,event,NOW+timedelta(days=32))
                sub=db.rows[Subscription][0]
                self.assertEqual(sub.status,'expired');self.assertEqual(sub.start_date,NOW)
                self.assertLess(sub.end_date,NOW+timedelta(days=32))
                self.assertEqual(db.rows[CreditTransaction][0].period_end,sub.end_date)
                helper.assert_free_unchanged(db)
