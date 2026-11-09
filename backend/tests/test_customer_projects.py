"""Customer Project API tests against disposable SQLite only."""

from datetime import datetime
import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

import test_privacy
from app.database.base import Base
from app.models.ai_generation import AIGeneration
from app.models.credit_transaction import CreditTransaction
from app.models.customer_project import CustomerProject
from app.models.photography_plan import PhotographyPlan
from app.models.profile import UserProfile
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.repositories.user_repository import lock_profile
from app.services import subscription_service


class CustomerProjectTests(unittest.TestCase):
    auth = test_privacy.PrivacyTests.auth

    def setUp(self):
        test_privacy.PrivacyTests.setUp(self)
        for model in (
            UserProfile,
            SubscriptionPlan,
            Subscription,
            AIGeneration,
            CreditTransaction,
            CustomerProject,
            PhotographyPlan,
        ):
            model.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add_all(
                [
                    SubscriptionPlan(
                        id=1,
                        name="Free Basic",
                        user_role="owner",
                        monthly_credits=10,
                        price=0,
                        is_active=True,
                        max_projects=2,
                        max_share_links=3,
                        trial_days=None,
                        currency="LKR",
                        code="basic",
                    ),
                    SubscriptionPlan(
                        id=2,
                        name="Free Trial",
                        user_role="owner",
                        monthly_credits=100,
                        price=0,
                        is_active=True,
                        max_projects=10,
                        max_share_links=20,
                        trial_days=14,
                        currency="LKR",
                        code="trial",
                    ),
                    SubscriptionPlan(
                        id=3,
                        name="Paid Pro",
                        user_role="owner",
                        monthly_credits=500,
                        price=1500,
                        is_active=True,
                        max_projects=50,
                        max_share_links=100,
                        trial_days=None,
                        currency="LKR",
                        code="pro",
                    ),
                    UserProfile(
                        user_id=2,
                        onboarding_status="completed",
                        studio_name="Studio",
                        studio_phone="+94771234567",
                        studio_address="1 Test Road",
                        studio_city="Jaffna",
                    ),
                    User(id=4, name="Second Owner", email="owner4@example.invalid", role="owner"),
                    UserProfile(
                        user_id=4,
                        onboarding_status="completed",
                        studio_name="Second Studio",
                        studio_phone="+94771234568",
                        studio_address="2 Test Road",
                        studio_city="Jaffna",
                    ),
                ]
            )
            db.commit()
        self.now = datetime(2026, 1, 15, 12, 0)
        self.clock = patch.object(subscription_service, "clock", side_effect=lambda: self.now)
        self.clock.start()
        self.owner_headers = self.auth(2)
        self.second_owner_headers = self.auth(4)

    def tearDown(self):
        self.clock.stop()
        test_privacy.PrivacyTests.tearDown(self)

    def activate(self, plan="basic", owner_headers=None):
        return self.client.post(
            f"/owner/subscription/{plan}",
            headers=owner_headers or self.owner_headers,
            json={"idempotency_key": f"project-test-{plan}-key-00001"},
        )

    def create(self, name="Customer"):
        return self.client.post(
            "/owner/projects",
            headers=self.owner_headers,
            json={"customer_name": name, "event_type": "Portrait"},
        )

    def create_plan(self, headers=None):
        return self.client.post(
            "/owner/photography-plans",
            headers=headers or self.owner_headers,
            json={
                "photography_type": "Portrait",
                "people_count": 2,
                "environment": "Outdoor",
                "location": "Jaffna",
            },
        )

    def test_owner_crud_and_credits_are_unchanged(self):
        self.assertEqual(self.activate().status_code, 200)
        created = self.client.post(
            "/owner/projects",
            headers=self.owner_headers,
            json={
                "customer_name": "Customer",
                "project_title": "  Wedding Session  ",
                "customer_contact": "+94771234567",
                "event_type": "Portrait",
                "shoot_location": "  Jaffna Fort  ",
                "shooting_date": "2026-03-20",
                "requirements": "Indoor",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        self.assertEqual(body["customer_name"], "Customer")
        self.assertEqual(body["project_title"], "Wedding Session")
        self.assertEqual(body["customer_contact"], "+94771234567")
        self.assertEqual(body["event_type"], "Portrait")
        self.assertEqual(body["shoot_location"], "Jaffna Fort")
        self.assertEqual(body["shooting_date"], "2026-03-20")
        self.assertTrue(body["is_editable"])
        self.assertNotIn("deleted_at", body)

        listed = self.client.get("/owner/projects", headers=self.owner_headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([project["id"] for project in listed.json()], [body["id"]])
        self.assertEqual(listed.json()[0]["project_title"], "Wedding Session")
        detailed = self.client.get(
            f"/owner/projects/{body['id']}", headers=self.owner_headers
        )
        self.assertEqual(detailed.status_code, 200)
        self.assertEqual(detailed.json()["shoot_location"], "Jaffna Fort")
        updated = self.client.patch(
            f"/owner/projects/{body['id']}",
            headers=self.owner_headers,
            json={
                "customer_name": "Updated Customer",
                "project_title": "  Reception  ",
                "shoot_location": "  Point Pedro  ",
                "requirements": "Indoor\nNatural light",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["customer_name"], "Updated Customer")
        self.assertEqual(updated.json()["project_title"], "Reception")
        self.assertEqual(updated.json()["shoot_location"], "Point Pedro")
        self.assertEqual(updated.json()["requirements"], "Indoor\nNatural light")
        with Session(self.engine) as db:
            grants = list(db.scalars(select(CreditTransaction)))
            self.assertEqual(len(grants), 1)
            self.assertEqual(grants[0].credits_change, 10)

    def test_basic_project_limit_and_role_restrictions(self):
        self.assertEqual(self.activate().status_code, 200)
        self.assertEqual(self.create("One").status_code, 201)
        self.assertEqual(self.create("Two").status_code, 201)
        self.assertEqual(self.create("Three").status_code, 409)
        self.assertEqual(self.client.get("/owner/projects", headers=self.auth(1)).status_code, 403)
        self.assertEqual(self.client.get("/owner/projects", headers=self.auth(3)).status_code, 403)
        self.assertEqual(self.client.get("/owner/projects").status_code, 401)

    def test_trial_project_limit(self):
        self.assertEqual(self.activate("trial").status_code, 200)
        for index in range(10):
            response = self.create(f"Trial {index}")
            self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.create("Over limit").status_code, 409)

    def test_cross_owner_access_is_not_found(self):
        self.assertEqual(self.activate().status_code, 200)
        self.assertEqual(self.activate(owner_headers=self.second_owner_headers).status_code, 200)
        created = self.create()
        project_id = created.json()["id"]
        for response in (
            self.client.get(f"/owner/projects/{project_id}", headers=self.second_owner_headers),
            self.client.patch(
                f"/owner/projects/{project_id}",
                headers=self.second_owner_headers,
                json={"customer_name": "Not mine"},
            ),
        ):
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/owner/projects", headers=self.second_owner_headers).json(), [])

    def test_project_plans_create_list_and_link_are_owner_scoped(self):
        self.assertEqual(self.activate().status_code, 200)
        project = self.create().json()
        created = self.client.post(
            f"/owner/projects/{project['id']}/photography-plans",
            headers=self.owner_headers,
            json={
                "photography_type": "Portrait",
                "people_count": 2,
                "environment": "Outdoor",
                "location": "Jaffna",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["project_id"], project["id"])

        unlinked = self.create_plan()
        self.assertEqual(unlinked.status_code, 201, unlinked.text)
        self.assertIsNone(unlinked.json()["project_id"])
        linked = self.client.post(
            f"/owner/projects/{project['id']}/photography-plans/{unlinked.json()['id']}",
            headers=self.owner_headers,
        )
        self.assertEqual(linked.status_code, 200, linked.text)
        self.assertEqual(linked.json()["project_id"], project["id"])

        listed = self.client.get(
            f"/owner/projects/{project['id']}/photography-plans",
            headers=self.owner_headers,
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(
            {plan["id"] for plan in listed.json()},
            {created.json()["id"], unlinked.json()["id"]},
        )
        self.assertEqual(
            self.client.post(
                f"/owner/projects/{project['id']}/photography-plans/{unlinked.json()['id']}",
                headers=self.owner_headers,
            ).status_code,
            409,
        )

    def test_project_plan_operations_reject_invalid_and_cross_owner_ids(self):
        self.assertEqual(self.activate().status_code, 200)
        self.assertEqual(self.activate(owner_headers=self.second_owner_headers).status_code, 200)
        project_id = self.create().json()["id"]
        second_project_id = self.client.post(
            "/owner/projects",
            headers=self.second_owner_headers,
            json={"customer_name": "Second Owner Project"},
        ).json()["id"]
        own_plan = self.create_plan().json()
        second_plan = self.create_plan(self.second_owner_headers).json()

        for response in (
            self.client.post(
                f"/owner/projects/{second_project_id}/photography-plans",
                headers=self.owner_headers,
                json={
                    "photography_type": "Portrait",
                    "people_count": 2,
                    "environment": "Outdoor",
                },
            ),
            self.client.get(
                f"/owner/projects/{second_project_id}/photography-plans",
                headers=self.owner_headers,
            ),
            self.client.post(
                f"/owner/projects/{second_project_id}/photography-plans/{own_plan['id']}",
                headers=self.owner_headers,
            ),
            self.client.post(
                f"/owner/projects/{project_id}/photography-plans/{second_plan['id']}",
                headers=self.owner_headers,
            ),
            self.client.get(
                "/owner/projects/9876/photography-plans", headers=self.owner_headers
            ),
            self.client.post(
                "/owner/projects/9876/photography-plans",
                headers=self.owner_headers,
                json={
                    "photography_type": "Portrait",
                    "people_count": 2,
                    "environment": "Outdoor",
                },
            ),
        ):
            self.assertEqual(response.status_code, 404, response.text)

    def test_read_only_projects_allow_listing_but_block_plan_changes(self):
        activated = self.activate("trial")
        self.assertEqual(activated.status_code, 200)
        project_ids = [self.create(f"Trial {index}").json()["id"] for index in range(3)]
        linked = self.client.post(
            f"/owner/projects/{project_ids[2]}/photography-plans",
            headers=self.owner_headers,
            json={
                "photography_type": "Portrait",
                "people_count": 2,
                "environment": "Outdoor",
            },
        )
        self.assertEqual(linked.status_code, 201, linked.text)
        unlinked = self.create_plan()
        self.assertEqual(unlinked.status_code, 201, unlinked.text)
        self.now = datetime.fromisoformat(activated.json()["period_end"])

        listed = self.client.get(
            f"/owner/projects/{project_ids[2]}/photography-plans",
            headers=self.owner_headers,
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["id"] for item in listed.json()], [linked.json()["id"]])
        self.assertEqual(
            self.client.post(
                f"/owner/projects/{project_ids[2]}/photography-plans",
                headers=self.owner_headers,
                json={
                    "photography_type": "Wedding",
                    "people_count": 2,
                    "environment": "Indoor",
                },
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                f"/owner/projects/{project_ids[2]}/photography-plans/{unlinked.json()['id']}",
                headers=self.owner_headers,
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.patch(
                f"/owner/photography-plans/{linked.json()['id']}",
                headers=self.owner_headers,
                json={"location": "Changed"},
            ).status_code,
            409,
        )

    def test_expired_trial_preserves_all_projects_but_only_oldest_two_are_editable(self):
        activated = self.activate("trial")
        self.assertEqual(activated.status_code, 200)
        project_ids = [self.create(f"Trial {index}").json()["id"] for index in range(4)]
        self.now = datetime.fromisoformat(activated.json()["period_end"])

        listed = self.client.get("/owner/projects", headers=self.owner_headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()], project_ids)
        self.assertEqual([item["is_editable"] for item in listed.json()], [True, True, False, False])
        self.assertEqual(
            self.client.patch(
                f"/owner/projects/{project_ids[0]}",
                headers=self.owner_headers,
                json={"customer_name": "Still editable"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                f"/owner/projects/{project_ids[2]}",
                headers=self.owner_headers,
                json={"customer_name": "Must remain read-only"},
            ).status_code,
            409,
        )
        with Session(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(CustomerProject)))), 4)

    def test_pro_limit_is_50_without_payment_activation(self):
        with Session(self.engine) as db:
            db.add(
                Subscription(
                    user_id=2,
                    plan_id=3,
                    plan_kind="pro",
                    start_date=self.now,
                    end_date=None,
                    status="active",
                    activation_key=b"p" * 32,
                )
            )
            db.commit()
            db.add_all(
                CustomerProject(
                    studio_owner_id=2,
                    customer_name=f"Project {index}",
                )
                for index in range(50)
            )
            db.commit()
        response = self.client.get("/owner/projects", headers=self.owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 50)
        self.assertTrue(all(project["is_editable"] for project in response.json()))
        self.assertEqual(self.create("51st project").status_code, 409)
        self.assertEqual(
            self.client.post(
                "/owner/subscription/pro",
                headers=self.owner_headers,
                json={"idempotency_key": "pro-checkout-stays-disabled"},
            ).status_code,
            404,
        )

    def test_soft_deleted_projects_are_hidden_and_do_not_use_a_slot(self):
        self.assertEqual(self.activate().status_code, 200)
        created = self.create()
        project_id = created.json()["id"]
        with Session(self.engine) as db:
            db.get(CustomerProject, project_id).deleted_at = self.now
            db.commit()
        self.assertEqual(self.client.get("/owner/projects", headers=self.owner_headers).json(), [])
        self.assertEqual(
            self.client.get(f"/owner/projects/{project_id}", headers=self.owner_headers).status_code,
            404,
        )
        self.assertEqual(self.create("Replacement").status_code, 201)

    def test_project_title_and_shoot_location_validation(self):
        self.assertEqual(self.activate().status_code, 200)
        for field, value in (
            ("project_title", "x" * 151),
            ("shoot_location", "x" * 256),
            ("project_title", "Bad\x00title"),
            ("shoot_location", "Bad\x00location"),
        ):
            self.assertEqual(
                self.client.post(
                    "/owner/projects",
                    headers=self.owner_headers,
                    json={"customer_name": "Customer", field: value},
                ).status_code,
                422,
            )
        created = self.client.post(
            "/owner/projects",
            headers=self.owner_headers,
            json={
                "customer_name": "Customer",
                "project_title": "x" * 150,
                "shoot_location": "y" * 255,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(len(created.json()["project_title"]), 150)
        self.assertEqual(len(created.json()["shoot_location"]), 255)

    def test_create_locks_owner_before_checking_project_limit(self):
        self.assertEqual(self.activate().status_code, 200)
        events = []

        def lock_and_record(db, user_id):
            events.append("owner_lock")
            return lock_profile(db, user_id)

        from app.repositories import project_repository

        count_active = project_repository.count_active

        def count_and_record(db, owner_id):
            events.append("limit_count")
            return count_active(db, owner_id)

        with (
            patch("app.services.project_service.lock_profile", side_effect=lock_and_record),
            patch.object(project_repository, "count_active", side_effect=count_and_record),
        ):
            response = self.create()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertLess(events.index("owner_lock"), events.index("limit_count"), events)


if __name__ == "__main__":
    unittest.main()
