"""AI integration: disposable SQLite/files and mocked HTTP only; no live provider."""

import base64
from dataclasses import replace
import io
import json
import logging
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import select, func
from sqlalchemy.orm import Session

import test_free_generation
from app.database.connection import get_db
from app.main import app
from app.models.ai_generation import AIGeneration
from app.models.ai_result import AIResult
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.models.photography_plan import PhotographyPlan
from app.services import ai_image_storage as storage, ai_service, pollinations_service as provider
from app.services import free_generation_service as allowance
from app.services.generation_planning import planned_shots
from app.schemas.ai import ImageGuidance, CameraSetupGuide
from pydantic import ValidationError


def png(color):
    output = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(output, format="PNG")
    return output.getvalue()


IMAGES = [png(color) for color in ("red", "green", "blue", "yellow")]


class GenerationTests(unittest.TestCase):
    auth = test_free_generation.FreeGenerationTests.auth

    def setUp(self):
        test_free_generation.FreeGenerationTests.setUp(self)
        def isolated_db():
            with Session(self.engine, expire_on_commit=False, autoflush=False) as db:
                yield db
        app.dependency_overrides[get_db] = isolated_db
        AIResult.__table__.create(self.engine)
        MediaAsset.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add(User(id=4, name="Other", email="other@example.invalid", role="user"))
            db.commit()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        for module, values in ((storage, {"ai_image_dir": str(self.root)}),
                               (provider, {"pollinations_enabled": True, "pollinations_api_key": "unit-test-placeholder"})):
            patcher = patch.object(module, "settings", replace(module.settings, **values))
            patcher.start(); self.addCleanup(patcher.stop)
        self.provider_patch = patch.object(provider, "generate_images", return_value=IMAGES)
        self.mock_provider = self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

    def tearDown(self):
        test_free_generation.FreeGenerationTests.tearDown(self)

    def generate(self, **kwargs):
        return self.client.post("/ai/generations", headers=kwargs.pop("headers", self.headers),
                                data=kwargs.pop("data", {"plan_id": "1", "description": "A person in a garden"}), **kwargs)

    def status(self):
        return self.client.get("/ai/free-generation/eligibility", headers=self.headers).json()["free_request_status"]

    def test_success_persists_four_and_consumes_once_with_private_retrieval(self):
        response = self.generate(files={"reference": ("portrait.png", IMAGES[0], "image/png")})
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(len(result["images"]), 4)
        self.assertEqual(self.status(), "used")
        self.assertNotIn("prompt", response.text)
        self.assertNotIn("file_url", response.text)
        self.assertNotIn("unit-test-placeholder", response.text)
        self.assertIsNotNone(self.mock_provider.call_args.args[1])
        with Session(self.engine, autoflush=False) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AIResult)), 4)
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)), 4)
        for item in result["images"]:
            image = self.client.get(item["url"], headers=self.headers)
            self.assertEqual(image.status_code, 200)
            self.assertIn("no-store", image.headers["cache-control"])
            self.assertEqual(self.client.get(item["url"]).status_code, 401)
            self.assertEqual(self.client.get(item["url"], headers=self.auth(4)).status_code, 404)
        self.assertEqual(self.client.get("/ai/generations", headers=self.auth(4)).json(), [])
        self.assertEqual(self.generate().status_code, 409)
        self.mock_provider.assert_called_once()
        self.assertEqual(len(list(self.root.iterdir())), 4)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in self.root.iterdir()))

    def test_consumed_allowance_rejects_before_pollinations_and_creates_no_more_images(self):
        first = self.generate()
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(len(first.json()["images"]), 4)
        self.mock_provider.assert_called_once()
        original_files = set(self.root.iterdir())
        with Session(self.engine, autoflush=False) as db:
            original_assets = db.scalar(select(func.count()).select_from(MediaAsset))
            original_generations = db.scalar(select(func.count()).select_from(AIGeneration))

        rejected = self.generate()
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.mock_provider.assert_called_once()
        self.assertEqual(set(self.root.iterdir()), original_files)
        with Session(self.engine, autoflush=False) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)), original_assets)
            self.assertEqual(db.scalar(select(func.count()).select_from(AIGeneration)), original_generations)

    def test_saved_plan_is_used_without_description_and_guidance_survives_plan_edit(self):
        with Session(self.engine) as db:
            plan = db.get(PhotographyPlan, 1)
            plan.photography_type = "Graduation"
            plan.location = "Botanical garden"
            plan.people_count = 2
            plan.preferences = {
                "clothing_style": "Formal", "outfit_details": "Blue suit, silver watch",
                "outfit_color": "Blue", "extra_instructions": "Keep the flowers visible.\nNo hats.",
                "lighting_preference": "Golden Hour", "camera_angle_preference": "Low Angle",
                "pose_preference": "Candid", "photography_style": "Natural",
                "equipment": {"device_type": "Smartphone"},
            }
            db.commit()
        response = self.generate(data={"plan_id": "1"})
        self.assertEqual(response.status_code, 201, response.text)
        prompt = self.mock_provider.call_args.args[0]
        for text in ("Graduation", "Botanical garden", "Number of people: 2", "Formal",
                     "Blue suit, silver watch", "Keep the flowers visible.", "No hats.",
                     "Golden Hour", "Low Angle", "Candid", "Natural", "Smartphone"):
            self.assertIn(text, prompt)
        shots = self.mock_provider.call_args.kwargs["shots"]
        self.assertEqual(len({s["pose_name"] for s in shots}), 4)
        self.assertEqual(len({s["camera_angle"] for s in shots}), 4)
        self.assertEqual([image["guidance"] for image in response.json()["images"]], shots)
        for shot in shots:
            self.assertEqual(len(shot["camera_setup"]["steps"]), 7)
            self.assertIn("smartphone", shot["camera_setup"]["suggested_lens_or_zoom"])
            self.assertIn("low sun", shot["camera_setup"]["lighting_direction"])
        self.assertEqual(len({tuple(s["camera_setup"]["steps"]) for s in shots}), 4)
        with Session(self.engine) as db:
            db.get(PhotographyPlan, 1).preferences = {"pose_preference": "Formal"}
            db.commit()
        # A fresh authenticated request/session reads the persisted snapshot, not plan edits.
        self.assertEqual(self.client.get("/ai/generations").status_code, 401)
        gallery = self.client.get("/ai/generations", headers=self.auth(1)).json()
        self.assertEqual(gallery[0]["images"], response.json()["images"])
        old_shots = {str(image["id"]): {key: value for key, value in image["guidance"].items() if key != "camera_setup"}
                     for image in response.json()["images"]}
        with Session(self.engine) as db:
            db.get(AIGeneration, response.json()["id"]).guidance_text = json.dumps({"version": 1, "images": old_shots})
            db.commit()
        legacy_images = self.client.get("/ai/generations", headers=self.auth(1)).json()[0]["images"]
        for image in legacy_images:
            self.assertIsNone(image["guidance"]["camera_setup"])
            self.assertEqual(image["guidance"]["pose_name"], old_shots[str(image["id"])]["pose_name"])
        for legacy in (None, "old unstructured text", '{"version":1,"images":[]}'):
            with Session(self.engine) as db:
                db.get(AIGeneration, response.json()["id"]).guidance_text = legacy
                db.commit()
            gallery = self.client.get("/ai/generations", headers=self.headers).json()
            self.assertTrue(all(image["guidance"] is None for image in gallery[0]["images"]))

    def test_additional_description_supplements_plan(self):
        response = self.generate(data={"plan_id": "1", "description": "Gentle smile"})
        self.assertEqual(response.status_code, 201)
        prompt = self.mock_provider.call_args.args[0]
        self.assertIn("Gentle smile", prompt)
        self.assertIn("Photography type:", prompt)
        self.assertIn("Environment: Outdoor", prompt)

    def test_failure_partial_duplicates_and_write_failure_release(self):
        for failure in (HTTPException(502, "Unavailable"), [IMAGES[0]], [IMAGES[0]] * 4):
            self.mock_provider.side_effect = failure if isinstance(failure, Exception) else None
            self.mock_provider.return_value = failure
            self.assertIn(self.generate().status_code, (502, 503))
            self.assertEqual(self.status(), "available")
            self.assertEqual(list(self.root.iterdir()), [])
        self.mock_provider.side_effect = None
        self.mock_provider.return_value = IMAGES
        with patch.object(storage, "write_image", side_effect=OSError("sensitive filesystem path")):
            with self.assertLogs("app.services.ai_service", level=logging.WARNING) as logs:
                self.assertEqual(self.generate().status_code, 503)
        self.assertIn("stage=storage_error", logs.output[0])
        self.assertIn("exception_category=OSError", logs.output[0])
        self.assertNotIn("sensitive filesystem path", "\n".join(logs.output))
        self.assertEqual(self.status(), "available")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)), 0)
        self.assertEqual(self.generate().status_code, 201)

    def test_validation_and_authorization_before_provider(self):
        for headers, expected in (({}, 401), (self.auth(2), 403), (self.auth(4), 404)):
            self.assertEqual(self.generate(headers=headers).status_code, expected)
        for content, mime, expected in ((b"not an image", "image/png", 422),
                                        (b"<svg/>", "image/svg+xml", 422),
                                        (b"x" * (storage.MAX_UPLOAD + 1), "image/png", 413)):
            self.assertEqual(self.generate(files={"reference": ("bad", content, mime)}).status_code, expected)
        self.assertEqual(self.generate(data={"plan_id": "1", "description": "x" * 2001}).status_code, 422)
        self.assertEqual(self.status(), "available")
        self.mock_provider.assert_not_called()

    def test_request_body_bound_before_multipart_parsing(self):
        response = self.client.post("/ai/generations", headers={**self.headers, "Content-Type": "application/octet-stream"},
                                    content=b"x" * (6 * 1024 * 1024 + 1))
        self.assertEqual(response.status_code, 413)
        self.mock_provider.assert_not_called()
        self.assertEqual(self.status(), "available")

    def test_partial_file_write_is_cleaned_up(self):
        original = storage.write_image
        count = 0
        def write(data):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("disk full")
            return original(data)
        with patch.object(storage, "write_image", side_effect=write):
            self.assertEqual(self.generate().status_code, 503)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.status(), "available")

    def test_disabled_provider_does_not_reserve(self):
        with patch.object(provider, "settings", replace(provider.settings, pollinations_enabled=False)):
            self.assertEqual(self.generate().status_code, 503)
        self.assertEqual(self.status(), "available")
        self.mock_provider.assert_not_called()

    def test_active_reservation_blocks_provider(self):
        with Session(self.engine) as db:
            allowance.reserve_free_request(db, db.get(User, 1), plan_id=1, quality="standard")
        self.assertEqual(self.generate().status_code, 409)
        self.mock_provider.assert_not_called()

    def test_unconfirmed_commit_retains_files_and_never_releases_claim(self):
        with patch.object(allowance, "complete_free_request", side_effect=RuntimeError("ack lost")):
            self.assertEqual(self.generate().status_code, 503)
        self.assertEqual(self.status(), "in_progress")
        self.assertEqual(len(list(self.root.iterdir())), 4)
        self.assertEqual(self.generate().status_code, 409)

    def test_commit_ack_lost_after_success_keeps_images_and_prevents_second_call(self):
        original = allowance.complete_free_request
        def committed(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("ack lost")
        with patch.object(allowance, "complete_free_request", side_effect=committed):
            self.assertEqual(self.generate().status_code, 503)
        self.assertEqual(self.status(), "used")
        gallery = self.client.get("/ai/generations", headers=self.headers).json()
        self.assertEqual(len(gallery[0]["images"]), 4)
        self.assertEqual(self.generate().status_code, 409)
        self.mock_provider.assert_called_once()


class ProviderTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(provider, "settings", replace(provider.settings,
            pollinations_enabled=True, pollinations_api_key="unit-test-placeholder"))
        patcher.start(); self.addCleanup(patcher.stop)

    def run_provider(self, handler, reference=None, generation_id=None):
        with patch.object(provider.httpx, "HTTPTransport", return_value=httpx.MockTransport(handler)):
            return provider.generate_images(
                "One person, same clothes", reference, generation_id=generation_id
            )

    def test_two_owner_locations_reach_mocked_provider(self):
        from app.services import generation_planning as planning
        from app.schemas.owner_ai import OwnerGenerationPreferences
        preferences = OwnerGenerationPreferences().model_dump()
        preferences.update(background_mode='different', outfit_mode='same')
        plan = SimpleNamespace(preferences={}, people_count=1)
        with patch.object(planning, 'BATCH_SIZE', 2):
            shots = planning.planned_owner_shots(plan, preferences)
        requests = []
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(IMAGES[len(requests)-1]).decode()}]})
        with patch.object(provider.httpx, 'HTTPTransport', return_value=httpx.MockTransport(handler)):
            images = provider.generate_images('Saved garden plan', None, shots=shots)
        self.assertEqual(len(images), 2)
        self.assertIn('sandy ocean beach', requests[0]['prompt'])
        self.assertIn('urban plaza', requests[1]['prompt'])
        self.assertTrue(all('same outfit' in request['prompt'] for request in requests))

    def test_saved_camera_preference_changes_matching_provider_and_guidance_specs(self):
        for angle, position in (("Low Angle", "below"), ("High Angle", "above"),
                                ("Eye Level", "eye level"), ("Side Angle", "eye level")):
            shots = planned_shots(SimpleNamespace(preferences={"camera_angle_preference": angle, "pose_preference": "Formal"}))
            self.assertEqual(len({shot["camera_angle"] for shot in shots}), 4)
            for shot in shots:
                self.assertIn(angle, shot["camera_angle"])
                self.assertIn(position, shot["camera_position"])
                self.assertIn("Formal", shot["pose_name"])
            requests = []
            def handler(request):
                requests.append(json.loads(request.content))
                return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(IMAGES[len(requests)-1]).decode()}]})
            with patch.object(provider.httpx, "HTTPTransport", return_value=httpx.MockTransport(handler)):
                provider.generate_images("Saved plan details", None, shots=shots)
            for shot, body in zip(shots, requests):
                self.assertEqual(json.loads(body["prompt"].split("\nShot specification: ", 1)[1]), shot)

    def test_setup_fields_are_practical_distinct_and_follow_equipment_and_lighting(self):
        for device, lighting, expected_light in (
            ("Smartphone", "Golden Hour", "low sun"),
            ("Mirrorless", "Studio Light", "studio light"),
            (None, "Low Light", "lamp"),
            (None, "Natural Light", "daylight"),
        ):
            shots = planned_shots(SimpleNamespace(people_count=3, preferences={
                "lighting_preference": lighting, "equipment": {"device_type": device, "lens": "50 mm prime"},
            }))
            self.assertEqual(len({s["camera_setup"]["camera_distance"] for s in shots}), 4)
            self.assertEqual(len({s["camera_setup"]["subject_position"] for s in shots}), 4)
            for shot in shots:
                setup = ImageGuidance.model_validate(shot).camera_setup
                self.assertEqual(len(setup.steps), 7)
                self.assertIn("Approximate", setup.camera_distance)
                self.assertIn("approximate", setup.suggested_lens_or_zoom)
                self.assertIn("50 mm prime", setup.suggested_lens_or_zoom)
                self.assertIn(expected_light, setup.lighting_direction)
                self.assertIn("everyone", setup.camera_distance)
                self.assertIn("every face", setup.steps[-1])
                self.assertIn("hands", setup.subject_position)
                self.assertIn(setup.camera_direction_and_tilt, setup.steps)
            with self.assertRaises(ValidationError):
                CameraSetupGuide.model_validate({**shots[0]["camera_setup"], "steps": ["Too short"]})

    def test_setup_tolerates_legacy_malformed_optional_preferences(self):
        for preferences in (None, "invalid JSON", [], {"lighting_preference": {}, "equipment": []}):
            shots = planned_shots(SimpleNamespace(preferences=preferences))
            self.assertEqual(len(shots), 4)
            for shot in shots:
                self.assertEqual(len(ImageGuidance.model_validate(shot).camera_setup.steps), 7)

    def test_official_text_and_edit_contract_four_distinct_prompts(self):
        for reference in (None, IMAGES[0]):
            requests = []
            def handler(request):
                requests.append(request)
                return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(IMAGES[len(requests)-1]).decode()}]})
            images = self.run_provider(handler, reference)
            self.assertEqual(len(set(images)), 4)
            bodies = [json.loads(r.content) for r in requests]
            self.assertEqual(len({b["prompt"] for b in bodies}), 4)
            for shot, body in zip(planned_shots(), bodies):
                self.assertEqual(json.loads(body["prompt"].split("\nShot specification: ", 1)[1]), shot)
                self.assertEqual(body["model"], provider.settings.pollinations_image_model)
            for request, body in zip(requests, bodies):
                self.assertEqual(request.url.path, "/v1/images/edits" if reference else "/v1/images/generations")
                self.assertEqual(body["response_format"], "b64_json")
                self.assertEqual(body["n"], 1)
                self.assertEqual(request.headers["authorization"], "Bearer unit-test-placeholder")
                self.assertEqual("image" in body, reference is not None)
                if reference:
                    self.assertTrue(body["image"][0]["image_url"].startswith("data:image/png;base64,"))

    def test_rejected_malformed_duplicate_and_timeout_are_sanitized(self):
        cases = []
        for code in (400, 401, 402, 403, 429, 500):
            cases.append(lambda r, code=code: httpx.Response(code, text="secret-provider-error"))
        for body in ({}, {"data": []}, {"data": [{"url": "http://127.0.0.1/private"}]},
                     {"data": [{"b64_json": "invalid"}]}, {"data": [{"b64_json": base64.b64encode(IMAGES[0]).decode()}]}):
            cases.append(lambda r, body=body: httpx.Response(200, json=body))
        def timeout(request):
            raise httpx.ReadTimeout("secret-provider-error")
        cases.append(timeout)
        for handler in cases:
            with self.assertRaises(HTTPException) as raised:
                self.run_provider(handler)
            self.assertEqual(raised.exception.status_code, 502)
            self.assertNotIn("secret", raised.exception.detail)

    def test_diagnostics_classify_provider_failures_without_sensitive_data(self):
        private_key = "private-test-api-key"
        private_prompt = "fictional subject with private prompt marker"
        with patch.object(
            provider,
            "settings",
            replace(
                provider.settings,
                pollinations_enabled=True,
                pollinations_api_key=private_key,
            ),
        ):
            cases = (
                (
                    "provider_http_error",
                    lambda request: httpx.Response(429, text=private_prompt),
                    "http_status=429",
                ),
                (
                    "timeout",
                    lambda request: (_ for _ in ()).throw(httpx.ReadTimeout(private_prompt)),
                    "exception_category=ReadTimeout",
                ),
                (
                    "connection_error",
                    lambda request: (_ for _ in ()).throw(httpx.ConnectError(private_prompt)),
                    "exception_category=ConnectError",
                ),
                (
                    "invalid_json",
                    lambda request: httpx.Response(200, content=private_prompt.encode()),
                    "validation_stage=response_json",
                ),
                (
                    "invalid_base64",
                    lambda request: httpx.Response(
                        200, json={"data": [{"b64_json": "invalid"}]}
                    ),
                    "validation_stage=base64_decode",
                ),
                (
                    "response_validation_error",
                    lambda request: httpx.Response(200, json={"data": []}),
                    "validation_stage=response_shape",
                ),
                (
                    "image_validation_error",
                    lambda request: httpx.Response(
                        200,
                        json={"data": [{"b64_json": base64.b64encode(b"not an image").decode()}]},
                    ),
                    "validation_stage=image_validation",
                ),
            )
            for stage, handler, expected_field in cases:
                with self.subTest(stage=stage):
                    with self.assertLogs("app.services.pollinations_service", level=logging.WARNING) as logs:
                        with self.assertRaises(HTTPException):
                            self.run_provider(handler, generation_id=67890)
                    output = "\n".join(logs.output)
                    self.assertIn("generation_id=67890", output)
                    self.assertIn(f"stage={stage}", output)
                    self.assertIn(expected_field, output)
                    self.assertRegex(output, r"elapsed_ms=\d+")
                    self.assertNotIn(private_key, output)
                    self.assertNotIn(private_prompt, output)
                    self.assertNotIn("Authorization", output)

    def test_timeout_diagnostic_does_not_reuse_prior_image_http_status(self):
                    requests = []

                    def responder(request):
                        requests.append(request)
                        if len(requests) == 1:
                            return httpx.Response(
                                200,
                                json={"data": [{"b64_json": base64.b64encode(IMAGES[0]).decode()}]},
                            )
                        raise httpx.ReadTimeout("private timeout detail")

                    with patch.object(provider.httpx, "HTTPTransport", return_value=httpx.MockTransport(responder)):
                        with self.assertLogs("app.services.pollinations_service", level="WARNING") as logs:
                            with self.assertRaises(HTTPException):
                                provider.generate_images(
                                    "One person, same clothes",
                                    None,
                                    shots=[{}, {}, {}, {}],
                                    generation_id=24680,
                                )
                    timeout_log = next(line for line in logs.output if "stage=timeout" in line)
                    self.assertIn("generation_id=24680", timeout_log)
                    self.assertIn("image_index=2", timeout_log)
                    self.assertIn("http_status=none", timeout_log)
                    self.assertNotIn("private timeout detail", timeout_log)

    def test_provider_request_and_status_diagnostics_are_correlated_and_safe(self):
        private_key = "private-test-api-key"
        private_prompt = "fictional subject with private prompt marker"
        with patch.object(
            provider,
            "settings",
            replace(
                provider.settings,
                pollinations_enabled=True,
                pollinations_api_key=private_key,
            ),
        ):
            with self.assertLogs("app.services.pollinations_service", level="INFO") as logs:
                with self.assertRaises(HTTPException):
                    self.run_provider(
                        lambda request: httpx.Response(503, text=private_prompt),
                        generation_id=12345,
                    )
        output = "\n".join(logs.output)
        self.assertIn("generation_id=12345", output)
        self.assertIn("stage=provider_request", output)
        self.assertIn("stage=provider_response", output)
        self.assertIn("stage=provider_http_error", output)
        self.assertIn("http_status=503", output)
        self.assertRegex(output, r"elapsed_ms=\d+")
        self.assertNotIn(private_key, output)
        self.assertNotIn(private_prompt, output)
        self.assertNotIn("Authorization", output)

    def test_duplicate_images_have_distinct_validation_diagnostic(self):
        with self.assertLogs("app.services.pollinations_service", level=logging.WARNING) as logs:
            with self.assertRaises(HTTPException):
                self.run_provider(
                    lambda request: httpx.Response(
                        200,
                        json={"data": [{"b64_json": base64.b64encode(IMAGES[0]).decode()}]},
                    )
                )
        output = "\n".join(logs.output)
        self.assertIn("stage=duplicate_images", output)
        self.assertIn("validation_stage=distinct_image_check", output)
        self.assertNotIn("b64_json", output)

    def test_provider_failure_is_not_retried(self):
        requests = []

        def fail_once(request):
            requests.append(request)
            return httpx.Response(503)

        with self.assertRaises(HTTPException):
            self.run_provider(fail_once)
        self.assertEqual(len(requests), 1)
