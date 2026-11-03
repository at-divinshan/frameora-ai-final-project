"""Photography plan API tests use disposable SQLite only; live MySQL is forbidden."""

import unittest
import logging
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import engine as production_engine, get_db
from app.main import app
from app.models.ai_generation import AIGeneration
from app.models.photography_plan import PhotographyPlan
from app.models.user import User


@compiles(VARBINARY, "sqlite")
def sqlite_binary(type_, compiler, **kwargs):
    return "BLOB"


class PhotographyPlanApiTests(unittest.TestCase):
    def setUp(self):
        self.production_guard = patch.object(
            production_engine, "connect", side_effect=AssertionError("Live database forbidden")
        )
        self.production_guard.start()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        list(PhotographyPlan.__mapper__._sorted_tables)
        User.__table__.create(self.engine)
        PhotographyPlan.__table__.create(self.engine)
        AIGeneration.__table__.create(self.engine)
        with Session(self.engine) as db:
            for user_id, role in ((1, "user"), (2, "user"), (3, "owner"), (4, "admin")):
                db.add(User(
                    id=user_id,
                    name=f"Test {role}",
                    email=f"{role}{user_id}@example.invalid",
                    role=role,
                    password_hash=None,
                ))
            db.commit()

        def isolated_db():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(app)
        self.decoder = patch("app.core.dependencies.decode_access_token", side_effect=lambda token: token)
        self.decoder.start()
        self.headers = self.make_headers(1)

    @staticmethod
    def make_headers(user_id):
        return {"Authorization": "".join(("B", "e", "a", "r", "e", "r", " ", str(user_id)))}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.decoder.stop()
        self.engine.dispose()
        self.production_guard.stop()

    @staticmethod
    def payload(**overrides):
        return {
            "photography_type": "Portrait",
            "people_count": 2,
            "environment": "Outdoor",
            "location": "Jaffna",
            "shoot_datetime": "2026-11-15T10:30:00+05:30",
            "preferences": {"style": "natural"},
            **overrides,
        }

    def test_create_and_list_are_scoped_to_authenticated_normal_user(self):
        response = self.client.post("/plans", headers=self.headers, json=self.payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["cache-control"], "no-store")
        body = response.json()
        self.assertEqual(body["photography_type"], "Portrait")
        self.assertEqual(body["people_count"], 2)
        self.assertEqual(body["environment"], "Outdoor")
        self.assertEqual(body["location"], "Jaffna")
        self.assertEqual(body["shoot_datetime"], "2026-11-15T05:00:00")
        self.assertEqual(body["preferences"], {"style": "natural"})
        self.assertIsNone(body["project_id"])
        self.assertNotIn("user_id", body)

        other_response = self.client.post(
            "/plans", headers=self.make_headers(2),
            json=self.payload(photography_type="Wedding", location=None, shoot_datetime=None, preferences=None),
        )
        self.assertEqual(other_response.status_code, 201)
        own_plans = self.client.get("/plans", headers=self.headers)
        other_plans = self.client.get("/plans", headers=self.make_headers(2))
        self.assertEqual(own_plans.status_code, 200)
        self.assertEqual(own_plans.headers["cache-control"], "no-store")
        self.assertEqual(len(own_plans.json()), 1)
        self.assertEqual(own_plans.json()[0]["photography_type"], "Portrait")
        self.assertEqual(len(other_plans.json()), 1)
        self.assertEqual(other_plans.json()[0]["photography_type"], "Wedding")

    def test_empty_list_and_authentication_and_role_requirements(self):
        self.assertEqual(self.client.get("/plans", headers=self.headers).json(), [])
        self.assertEqual(self.client.get("/plans").status_code, 401)
        self.assertEqual(self.client.post("/plans", json=self.payload()).status_code, 401)
        for token in ("3", "4"):
            headers = self.make_headers(token)
            self.assertEqual(self.client.get("/plans", headers=headers).status_code, 403)
            self.assertEqual(self.client.post("/plans", headers=headers, json=self.payload()).status_code, 403)

    def test_validation_and_client_cannot_set_owner_or_project(self):
        invalid_payloads = (
            self.payload(photography_type=""),
            self.payload(photography_type="x" * 51),
            self.payload(people_count=0),
            self.payload(people_count=11),
            self.payload(people_count=True),
            self.payload(environment=""),
            self.payload(environment="x" * 21),
            self.payload(location="x" * 256),
            self.payload(unknown="not allowed"),
            self.payload(user_id=2),
            self.payload(project_id=99),
        )
        for invalid in invalid_payloads:
            with self.subTest(payload=invalid):
                response = self.client.post("/plans", headers=self.headers, json=invalid)
                self.assertEqual(response.status_code, 422)
        response = self.client.post(
            "/plans",
            headers={**self.headers, "Content-Type": "application/json"},
            content='{"photography_type":"Portrait","people_count":2,"environment":"Outdoor","preferences":not-json}',
        )
        self.assertEqual(response.status_code, 422)

    def test_get_patch_and_partial_null_updates_are_owner_scoped(self):
        created = self.client.post("/plans", headers=self.headers, json=self.payload()).json()
        plan_id = created["id"]

        response = self.client.get(f"/plans/{plan_id}", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["location"], "Jaffna")
        self.assertNotIn("user_id", response.json())

        other_user = self.make_headers(2)
        self.assertEqual(self.client.get(f"/plans/{plan_id}", headers=other_user).status_code, 404)
        self.assertEqual(
            self.client.patch(f"/plans/{plan_id}", headers=other_user, json={"location": "Hidden"}).status_code,
            404,
        )

        response = self.client.patch(
            f"/plans/{plan_id}",
            headers=self.headers,
            json={"photography_type": "Wedding"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["photography_type"], "Wedding")
        self.assertEqual(response.json()["location"], "Jaffna")
        self.assertEqual(response.json()["preferences"], {"style": "natural"})

        response = self.client.patch(
            f"/plans/{plan_id}",
            headers=self.headers,
            json={"location": None, "shoot_datetime": None, "preferences": None},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["location"])
        self.assertIsNone(response.json()["shoot_datetime"])
        self.assertIsNone(response.json()["preferences"])

        for field in ("photography_type", "people_count", "environment"):
            response = self.client.patch(
                f"/plans/{plan_id}",
                headers=self.headers,
                json={field: None},
            )
            self.assertEqual(response.status_code, 422, field)

        for invalid in (
            {"people_count": 0},
            {"people_count": 11},
            {"photography_type": "x" * 51},
            {"environment": "x" * 21},
            {"location": "x" * 256},
            {"shoot_datetime": "not-a-date"},
            {"id": 99},
            {"user_id": 2},
            {"project_id": 99},
            {"created_at": "2026-01-01T00:00:00"},
        ):
            with self.subTest(patch=invalid):
                self.assertEqual(
                    self.client.patch(f"/plans/{plan_id}", headers=self.headers, json=invalid).status_code,
                    422,
                )

    def test_missing_and_non_owned_plan_ids_are_indistinguishable(self):
        self.assertEqual(self.client.get("/plans/9876", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.patch("/plans/9876", headers=self.headers, json={}).status_code, 404)
        self.assertEqual(self.client.delete("/plans/9876", headers=self.headers).status_code, 404)

        created = self.client.post("/plans", headers=self.headers, json=self.payload()).json()
        other_user = self.make_headers(2)
        self.assertEqual(self.client.get(f"/plans/{created['id']}", headers=other_user).status_code, 404)
        self.assertEqual(
            self.client.patch(f"/plans/{created['id']}", headers=other_user, json={}).status_code,
            404,
        )
        self.assertEqual(self.client.delete(f"/plans/{created['id']}", headers=other_user).status_code, 404)
        self.assertEqual(self.client.get("/plans/9876").status_code, 401)
        for token in ("3", "4"):
            self.assertEqual(self.client.get("/plans/9876", headers=self.make_headers(token)).status_code, 403)

    def test_delete_is_safe_and_preserves_plans_with_generation_history(self):
        deletable = self.client.post("/plans", headers=self.headers, json=self.payload()).json()
        response = self.client.delete(f"/plans/{deletable['id']}", headers=self.headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(f"/plans/{deletable['id']}", headers=self.headers).status_code, 404)

        referenced = self.client.post("/plans", headers=self.headers, json=self.payload()).json()
        with Session(self.engine) as db:
            db.add(AIGeneration(
                user_id=1,
                plan_id=referenced["id"],
                model_name=None,
                quality="standard",
                status="completed",
                error_message=None,
                completed_at=None,
                guidance_text=None,
                is_favorite=False,
            ))
            db.commit()
        response = self.client.delete(f"/plans/{referenced['id']}", headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(f"/plans/{referenced['id']}", headers=self.headers).status_code, 200)


if __name__ == "__main__":
    unittest.main()
