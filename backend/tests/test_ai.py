"""AI integration: disposable SQLite/files and mocked HTTP only; no live provider."""

import base64
from dataclasses import replace
import io
import json
import logging
from pathlib import Path
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
from app.services import ai_image_storage as storage, ai_service, pollinations_service as provider
from app.services import free_generation_service as allowance


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
        self.assertEqual(self.generate(data={"plan_id": "1", "description": "   "}).status_code, 422)
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

    def run_provider(self, handler, reference=None):
        with patch.object(provider.httpx, "HTTPTransport", return_value=httpx.MockTransport(handler)):
            return provider.generate_images("One person, same clothes", reference)

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
                            self.run_provider(handler)
                    output = "\n".join(logs.output)
                    self.assertIn(f"stage={stage}", output)
                    self.assertIn(expected_field, output)
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
