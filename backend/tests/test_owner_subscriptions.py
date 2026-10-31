"""Disposable SQLite subscription tests; migration 003 and live MySQL are never used."""

from datetime import datetime
from unittest.mock import patch
import unittest

from sqlalchemy import Column, Integer, Table, select
from sqlalchemy.orm import Session

import test_privacy
from app.models.credit_transaction import CreditTransaction
from app.models.profile import UserProfile
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.database.base import Base
from app.services import subscription_service


class OwnerSubscriptionTests(unittest.TestCase):
    auth = test_privacy.PrivacyTests.auth

    def setUp(self):
        test_privacy.PrivacyTests.setUp(self)
        UserProfile.__table__.create(self.engine)
        SubscriptionPlan.__table__.create(self.engine)
        Subscription.__table__.create(self.engine)
        if "AIGeneration" not in Base.metadata.tables:
            Table("AIGeneration", Base.metadata, Column("id", Integer, primary_key=True))
        Base.metadata.tables["AIGeneration"].create(self.engine)
        CreditTransaction.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add_all([
                SubscriptionPlan(id=1, name="Free Basic", user_role="owner", monthly_credits=10,
                    price=0, is_active=True, max_projects=2, max_share_links=3,
                    trial_days=None, currency="LKR", code="basic"),
                SubscriptionPlan(id=2, name="Free Trial", user_role="owner", monthly_credits=100,
                    price=0, is_active=True, max_projects=10, max_share_links=20,
                    trial_days=14, currency="LKR", code="trial"),
                SubscriptionPlan(id=3, name="Paid Pro", user_role="owner", monthly_credits=500,
                    price=1500, is_active=True, max_projects=50, max_share_links=100,
                    trial_days=None, currency="LKR", code="pro"),
                UserProfile(user_id=2, onboarding_status="pending_plan", studio_name="Studio",
                    studio_phone="+94771234567", studio_address="1 Test Road", studio_city="Jaffna"),
            ])
            db.commit()
        self.headers = self.auth(2)
        self.now = datetime(2026, 1, 15, 12, 0)
        self.clock = patch.object(subscription_service, "clock", side_effect=lambda: self.now)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        test_privacy.PrivacyTests.tearDown(self)

    def activate(self, plan, key="request-key-000001"):
        return self.client.post(f"/owner/subscription/{plan}", headers=self.headers,
            json={"idempotency_key": key})

    def test_owner_catalogue_and_paid_activation_is_absent(self):
        response = self.client.get("/owner/plans", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([plan["code"] for plan in response.json()["plans"]], ["basic", "trial", "pro"])
        plans = {plan["code"]: plan for plan in response.json()["plans"]}
        self.assertEqual(plans["basic"]["credits"], 10)
        self.assertEqual(plans["trial"]["credits"], 100)
        self.assertEqual(plans["trial"]["trial_days"], 14)
        self.assertFalse(plans["pro"]["activation_available"])
        self.assertEqual(self.client.post("/owner/subscription/pro", headers=self.headers,
            json={"idempotency_key": "request-key-000002"}).status_code, 404)

    def test_basic_activation_is_idempotent_and_completes_onboarding(self):
        first = self.activate("basic")
        repeated = self.activate("basic")
        different_key = self.activate("basic", "request-key-000003")
        for response in (first, repeated, different_key):
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["plan"], "basic")
            self.assertEqual(response.json()["remaining_credits"], 10)
        self.assertEqual(first.json()["period_start"], repeated.json()["period_start"])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(UserProfile).where(UserProfile.user_id == 2)).onboarding_status, "completed")
            self.assertEqual(len(list(db.scalars(select(Subscription)))), 1)
            self.assertEqual(len(list(db.scalars(select(CreditTransaction)))), 1)

    def test_basic_anniversary_and_trial_can_be_started_once(self):
        self.assertEqual(self.activate("basic").status_code, 200)
        self.now = datetime(2026, 2, 15, 12, 0)
        monthly = self.client.get("/owner/subscription", headers=self.headers)
        self.assertEqual(monthly.status_code, 200)
        self.assertEqual(monthly.json()["remaining_credits"], 10)
        self.assertEqual(monthly.json()["period_start"], "2026-02-15T12:00:00")

        trial = self.activate("trial", "trial-key-00000001")
        self.assertEqual(trial.status_code, 200, trial.text)
        self.assertEqual(trial.json()["plan"], "trial")
        self.assertEqual(trial.json()["remaining_credits"], 100)
        self.assertFalse(trial.json()["trial_available"])
        self.assertEqual(trial.json()["period_end"], "2026-03-01T12:00:00")
        self.assertEqual(self.activate("trial", "trial-key-00000002").status_code, 409)

    def test_trial_expiry_uses_exact_timestamp_for_basic_fallback(self):
        trial = self.activate("trial")
        self.assertEqual(trial.status_code, 200, trial.text)
        expiry = datetime.fromisoformat(trial.json()["period_end"])
        self.now = expiry
        response = self.client.get("/owner/subscription", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["plan"], "basic")
        self.assertEqual(response.json()["period_start"], expiry.isoformat())
        self.assertEqual(response.json()["remaining_credits"], 10)
        self.assertFalse(response.json()["trial_available"])

    def test_expired_pro_falls_back_without_enabling_paid_activation(self):
        expiry = datetime(2026, 1, 10, 9, 30)
        with Session(self.engine) as db:
            db.add(Subscription(user_id=2, plan_id=3, plan_kind="pro",
                start_date=datetime(2025, 12, 10, 9, 30), end_date=expiry, status="active",
                activation_key=b"p" * 32))
            db.commit()
        self.now = datetime(2026, 1, 15, 12, 0)
        response = self.client.get("/owner/subscription", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["plan"], "basic")
        self.assertEqual(response.json()["period_start"], expiry.isoformat())

    def test_missing_migration_fails_closed_without_creating_data(self):
        CreditTransaction.__table__.drop(self.engine)
        Subscription.__table__.drop(self.engine)
        SubscriptionPlan.__table__.drop(self.engine)
        response = self.client.get("/owner/plans", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertIn("migration", response.json()["detail"])

    def test_non_owner_and_incomplete_studio_cannot_activate(self):
        self.assertEqual(self.client.get("/owner/plans", headers=self.auth(1)).status_code, 403)
        with Session(self.engine) as db:
            db.add(User(id=4, name="Legacy Owner", email="legacy@example.invalid", role="owner"))
            db.commit()
        response = self.client.post("/owner/subscription/basic", headers=self.auth(4),
            json={"idempotency_key": "request-key-000004"})
        self.assertEqual(response.status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(Subscription)))), 0)
            self.assertEqual(len(list(db.scalars(select(CreditTransaction)))), 0)


if __name__ == "__main__":
    unittest.main()

class SubscriptionAuditTests(unittest.TestCase):
    """Additional isolated regression cases for the reviewed edge cases."""
    auth = OwnerSubscriptionTests.auth
    setUp = OwnerSubscriptionTests.setUp
    tearDown = OwnerSubscriptionTests.tearDown
    activate = OwnerSubscriptionTests.activate
    def test_retry_trial_does_not_duplicate_grant(self):
        self.assertEqual(self.activate('trial').status_code, 200)
        self.assertEqual(self.activate('trial').status_code, 200)
        self.assertEqual(self.activate('trial', 'different-request-0001').status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(Subscription)))), 1)
            self.assertEqual(len(list(db.scalars(select(CreditTransaction)))), 1)
    def test_expiry_get_is_read_only_then_basic_materializes_exact_anchor(self):
        first = self.activate('trial')
        expiry = datetime.fromisoformat(first.json()['period_end'])
        self.now = datetime(2026, 4, 2)
        self.assertEqual(self.client.get('/owner/subscription',headers=self.headers).json()['plan'], 'basic')
        with Session(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(Subscription)))), 1)
        self.assertEqual(self.activate('basic','basic-after-expiry-0001').status_code, 200)
        with Session(self.engine) as db:
            active = db.scalar(select(Subscription).where(Subscription.status == 'active'))
            self.assertEqual(active.start_date, expiry)
            self.assertEqual(active.plan_kind,'basic')
    def test_month_end_anniversary_and_no_carryover(self):
        self.now=datetime(2026,1,31,12)
        self.assertEqual(self.activate('basic').status_code,200)
        self.now=datetime(2026,2,28,12)
        result=self.activate('basic','february-request-01').json()
        self.assertEqual(result['period_end'],'2026-03-31T12:00:00')
        self.assertEqual(result['remaining_credits'],10)
    def test_unknown_fields_and_key_conflict(self):
        self.assertEqual(self.activate('basic').status_code,200)
        self.assertEqual(self.activate('trial').status_code,409)
        response=self.client.post('/owner/subscription/trial',headers=self.headers,json={'idempotency_key':'valid-request-0001','user_id':1})
        self.assertEqual(response.status_code,422)
    def test_sri_lankan_phones(self):
        for phone in ('0771234567','+94771234567'):
            response=self.client.put('/owner/studio',headers=self.headers,json={'studio_name':'Studio','studio_phone':phone,'studio_address':'1 Test Road','studio_city':'Jaffna'})
            self.assertEqual(response.status_code,200)
