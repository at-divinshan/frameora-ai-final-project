"""Photography plan API tests use disposable SQLite only; live MySQL is forbidden."""

import unittest
import logging
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
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
from app.schemas.photography_suggestions import PhotographySuggestions
from app.services.photography_suggestions import build_suggestions_prompt
from app.services.suggestions_provider import (
    SuggestionsProviderError,
    UnconfiguredSuggestionsProvider,
    get_suggestions_provider,
)


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

    def test_equipment_is_optional_validated_and_merged_without_losing_preferences(self):
        created = self.client.post(
            "/plans",
            headers=self.headers,
            json=self.payload(preferences={
                "photography_style": "Natural",
                "unrelated_preference": "keep me",
                "equipment": {
                    "device_type": "Smartphone",
                    "camera_model": "Pixel",
                    "additional_equipment": "Tripod",
                },
            }),
        )
        self.assertEqual(created.status_code, 201)
        plan_id = created.json()["id"]
        self.assertEqual(
            created.json()["preferences"]["equipment"],
            {
                "device_type": "Smartphone",
                "camera_model": "Pixel",
                "additional_equipment": "Tripod",
            },
        )

        updated = self.client.patch(
            f"/plans/{plan_id}",
            headers=self.headers,
            json={"preferences": {"equipment": {"camera_model": "iPhone"}}},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["preferences"]["photography_style"], "Natural")
        self.assertEqual(updated.json()["preferences"]["unrelated_preference"], "keep me")
        self.assertEqual(updated.json()["preferences"]["equipment"], {
            "device_type": "Smartphone",
            "camera_model": "iPhone",
            "additional_equipment": "Tripod",
        })

        cleared = self.client.patch(
            f"/plans/{plan_id}",
            headers=self.headers,
            json={"preferences": {"equipment": {
                "device_type": None,
                "camera_model": None,
                "lens": None,
                "additional_equipment": None,
            }}},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertNotIn("equipment", cleared.json()["preferences"])
        self.assertEqual(cleared.json()["preferences"]["unrelated_preference"], "keep me")

        # Plans remain valid when no equipment details are supplied.
        no_equipment = self.client.post(
            "/plans", headers=self.headers, json=self.payload(preferences={"photography_style": "Cinematic"})
        )
        self.assertEqual(no_equipment.status_code, 201)
        self.assertNotIn("equipment", no_equipment.json()["preferences"])

        invalid_equipment = (
            {"device_type": "Drone"},
            {"camera_model": "x" * 101},
            {"lens": "x" * 101},
            {"additional_equipment": "x" * 301},
            {"unknown": "not allowed"},
        )
        for equipment in invalid_equipment:
            response = self.client.post(
                "/plans", headers=self.headers,
                json=self.payload(preferences={"equipment": equipment}),
            )
            self.assertEqual(response.status_code, 422, equipment)

    def test_suggestions_endpoint_authentication_ownership_contract_and_prompt(self):
        self.assertEqual(self.client.post("/plans/9876/suggestions").status_code, 401)
        for token in ("3", "4"):
            self.assertEqual(
                self.client.post(f"/plans/9876/suggestions", headers=self.make_headers(token)).status_code,
                403,
            )
        self.assertEqual(
            self.client.post("/plans/9876/suggestions", headers=self.headers).status_code,
            404,
        )

        created = self.client.post(
            "/plans",
            headers=self.headers,
            json=self.payload(preferences={
                "photography_style": "Natural",
                "equipment": {
                    "device_type": "Smartphone",
                    "camera_model": "Pixel 9",
                    "additional_equipment": "Tripod",
                },
            }),
        ).json()
        other_user = self.make_headers(2)
        self.assertEqual(
            self.client.post(
                f"/plans/{created['id']}/suggestions", headers=other_user
            ).status_code,
            404,
        )

        class FakeProvider:
            def __init__(self):
                self.prompt = None

            async def generate(self, prompt):
                self.prompt = prompt
                return PhotographySuggestions(
                    pose_suggestions=["Pose 1", "Pose 2", "Pose 3"],
                    camera_angles=["Angle 1", "Angle 2", "Angle 3"],
                    lighting_tips=["Light 1", "Light 2", "Light 3"],
                    camera_settings=["Setting 1", "Setting 2", "Setting 3"],
                    composition_tips=["Composition 1", "Composition 2", "Composition 3"],
                    photography_tools=["Tool 1", "Tool 2", "Tool 3"],
                )

        provider = FakeProvider()
        app.dependency_overrides[get_suggestions_provider] = lambda: provider
        try:
            response = self.client.post(
                f"/plans/{created['id']}/suggestions", headers=self.headers
            )
        finally:
            app.dependency_overrides.pop(get_suggestions_provider, None)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(set(result), {
            "pose_suggestions", "camera_angles", "lighting_tips",
            "camera_settings", "composition_tips", "photography_tools",
        })
        self.assertEqual(sum(len(items) for items in result.values()), 18)
        self.assertIn("Pixel 9", provider.prompt)
        self.assertIn("Smartphone", provider.prompt)
        self.assertIn("only the equipment listed above", provider.prompt)
        self.assertIn("photography_tools category must explain how to use the supplied equipment", provider.prompt)

        with Session(self.engine) as db:
            plan = db.get(PhotographyPlan, created["id"])
            plan.preferences = None
            prompt = build_suggestions_prompt(plan)
        self.assertIn("device-neutral guidance", prompt)
        self.assertIn("clearly labeled optional", prompt)

    def test_suggestions_endpoint_reports_unconfigured_provider_without_external_call(self):
        created = self.client.post("/plans", headers=self.headers, json=self.payload()).json()
        app.dependency_overrides[get_suggestions_provider] = UnconfiguredSuggestionsProvider
        try:
            response = self.client.post(
                f"/plans/{created['id']}/suggestions", headers=self.headers
            )
        finally:
            app.dependency_overrides.pop(get_suggestions_provider, None)
        self.assertEqual(response.status_code, 503)
        self.assertIn("not available yet", response.json()["detail"])

    def test_suggestions_endpoint_sanitizes_provider_failures(self):
        created = self.client.post("/plans", headers=self.headers, json=self.payload()).json()

        class FailedProvider:
            async def generate(self, prompt):
                raise SuggestionsProviderError("Provider details must not reach clients.")

        app.dependency_overrides[get_suggestions_provider] = FailedProvider
        try:
            response = self.client.post(
                f"/plans/{created['id']}/suggestions", headers=self.headers
            )
        finally:
            app.dependency_overrides.pop(get_suggestions_provider, None)

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("Provider details", response.text)

    def test_suggestions_response_requires_six_categories_and_three_short_strings_each(self):
        response = {
            "pose_suggestions": ["Pose 1", "Pose 2", "Pose 3"],
            "camera_angles": ["Angle 1", "Angle 2", "Angle 3"],
            "lighting_tips": ["Light 1", "Light 2", "Light 3"],
            "camera_settings": ["Setting 1", "Setting 2", "Setting 3"],
            "composition_tips": ["Composition 1", "Composition 2", "Composition 3"],
            "photography_tools": ["Tool 1", "Tool 2", "Tool 3"],
        }
        self.assertEqual(
            sum(len(items) for items in PhotographySuggestions.model_validate(response).model_dump().values()),
            18,
        )
        invalid_responses = []
        short_list = {**response, "camera_angles": ["Angle 1", "Angle 2"]}
        invalid_responses.append(short_list)
        extra_category = {**response, "other": ["Not allowed"]}
        invalid_responses.append(extra_category)
        blank_suggestion = {**response, "pose_suggestions": [" ", "Pose 2", "Pose 3"]}
        invalid_responses.append(blank_suggestion)
        long_suggestion = {**response, "pose_suggestions": ["x" * 241, "Pose 2", "Pose 3"]}
        invalid_responses.append(long_suggestion)
        for invalid in invalid_responses:
            with self.subTest(response=invalid):
                with self.assertRaises(ValidationError):
                    PhotographySuggestions.model_validate(invalid)

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
