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
        # Use production metadata as imported: no synthetic CustomerProject table.
        # Resolving flush ordering must work before any database operation, including
        # for project_id=None. The previous synthetic table masked the runtime failure.
        list(PhotographyPlan.__mapper__._sorted_tables)
        User.__table__.create(self.engine)
        PhotographyPlan.__table__.create(self.engine)
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
        self.headers = {"Authorization": "Bearer 1"}

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
            "/plans", headers={"Authorization": "Bearer 2"},
            json=self.payload(photography_type="Wedding", location=None, shoot_datetime=None, preferences=None),
        )
        self.assertEqual(other_response.status_code, 201)
        own_plans = self.client.get("/plans", headers=self.headers)
        other_plans = self.client.get("/plans", headers={"Authorization": "Bearer 2"})
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
            headers = {"Authorization": f"Bearer {token}"}
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

    def test_database_failure_logs_only_safe_diagnostics_and_keeps_generic_response(self):
        from sqlalchemy.exc import OperationalError

        private_message = "private SQL text and a personal field value"
        private_parameters = {"email": "person@example.invalid", "token": "private-token-marker"}
        database_error = OperationalError(
            "private raw SQL",
            private_parameters,
            Exception(private_message),
        )
        database_error.orig.sqlstate = "23000"
        with self.assertLogs("app.main", level=logging.ERROR) as captured:
            with patch.object(Session, "commit", side_effect=database_error):
                response = self.client.post("/plans", headers=self.headers, json=self.payload())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "The database is temporarily unavailable. Please try again later."},
        )
        self.assertIn("exception_class=OperationalError", captured.output[0])
        self.assertIn("driver_class=Exception", captured.output[0])
        self.assertIn("sqlstate=23000", captured.output[0])
        for secret in (*private_parameters.values(), private_message, "private raw SQL"):
            self.assertNotIn(secret, captured.output[0])
            self.assertNotIn(secret, response.text)


if __name__ == "__main__":
    unittest.main()
