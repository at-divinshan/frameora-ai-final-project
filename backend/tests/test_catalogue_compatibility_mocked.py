"""Catalogue validation only; synthetic rows, no SQL execution or provider calls."""
import unittest
from types import SimpleNamespace as Row
from unittest.mock import Mock
from decimal import Decimal
from fastapi import HTTPException
from app.core.owner_plans import BY_CODE
from app.core.stripe_prices import paid_plan
from app.services.subscription_service import plans, resolve_effective
from app.repositories.payment_repository import PaymentRepository
from datetime import datetime, timedelta


def owner(code):
    p = BY_CODE[code]
    return Row(id=list(BY_CODE).index(code)+1, code=code, name=p.name, user_role='owner',
               is_active=True, monthly_credits=p.credits, price=p.price, currency=p.currency,
               max_projects=p.max_projects, max_share_links=p.max_share_links, trial_days=p.trial_days)


class CatalogueTests(unittest.TestCase):
    def catalogue(self, extra=(), base=None):
        db = Mock()
        db.scalars.return_value = (base if base is not None else [owner('basic'), owner('trial')]) + list(extra)
        return plans(db)

    def test_fresh_catalogue_without_legacy_pro(self):
        result = self.catalogue([owner(c) for c in ('starter','growth','unlimited')])
        self.assertEqual(set(result), set(BY_CODE))
        self.assertIsNone(result['trial'].max_projects)

    def test_valid_legacy_recognized_and_expiry_retains_basic_fallback(self):
        legacy = Row(id=99,code='pro',name='Paid Pro',monthly_credits=500,price=1500,
                     currency='LKR',max_projects=50,max_share_links=100,trial_days=None)
        available = self.catalogue([legacy])
        self.assertIs(available['pro'], legacy)
        now = datetime(2026,1,1)
        old = Row(id=42, plan_kind='pro', end_date=now-timedelta(days=1), status='active')
        result = resolve_effective(Mock(), 1, old, available, now)
        self.assertEqual(result.plan_id, available['basic'].id)
        self.assertEqual(old.status, 'active')  # read-only resolution
        legacy.price = 1
        self.assertNotIn('pro', self.catalogue([legacy]))

    def test_basic_trial_required_and_exact(self):
        for code in ('basic','trial'):
            with self.subTest(missing=code), self.assertRaises(HTTPException):
                self.catalogue(base=[owner(c) for c in ('basic','trial') if c != code])
            for field in ('name','monthly_credits','price','currency','max_projects','max_share_links','trial_days'):
                rows = [owner('basic'),owner('trial')]
                setattr(next(p for p in rows if p.code == code), field, 'invalid')
                with self.subTest(code=code,field=field), self.assertRaises(HTTPException):
                    self.catalogue(base=rows)
        trial=owner('trial');trial.max_projects=10;trial.max_share_links=20
        with self.assertRaises(HTTPException): self.catalogue(base=[owner('basic'),trial])

    def test_malformed_paid_rows_not_recognized(self):
        for code in ('starter','growth','unlimited'):
            for field in ('name','monthly_credits','price','currency','max_projects','max_share_links','trial_days'):
                row=owner(code);setattr(row,field,'invalid')
                with self.subTest(code=code,field=field):
                    self.assertNotIn(code,self.catalogue([row]))

    def test_role_specific_checkout_queries_and_paid_trial_rejection(self):
        for role, code in [('user','starter'),('user','pro'),('owner','starter'),('owner','growth'),('owner','unlimited')]:
            expected=paid_plan(role,code)
            row=Row(name=expected.name,monthly_credits=expected.credits,
                price=Decimal(expected.amount_minor)/100,currency='LKR',max_projects=expected.max_projects,
                max_share_links=expected.max_share_links,trial_days=None)
            db=Mock();db.scalar.return_value=row
            repository=PaymentRepository(db)
            with self.subTest(role=role,code=code):
                self.assertIs(repository._plan(code,role),row)
                statement=db.scalar.call_args.args[0]
                params=statement.compile().params
                self.assertIn(role,params.values());self.assertIn(code,params.values())
                self.assertIn('is_active IS true',str(statement))
                row.trial_days=14
                with self.assertRaises(HTTPException):repository._plan(code,role)
                row.trial_days=None;row.monthly_credits+=1
                with self.assertRaises(HTTPException):repository._plan(code,role)
        with self.assertRaises(HTTPException): PaymentRepository(Mock())._plan('pro','owner')
        with self.assertRaises(HTTPException): PaymentRepository(Mock())._plan('growth','user')
