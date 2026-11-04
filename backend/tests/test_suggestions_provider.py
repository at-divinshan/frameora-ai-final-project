"""Pollinations suggestions provider tests use mocked HTTP transport only."""

import asyncio
import json
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.services.suggestions_provider import (
    POLLINATIONS_CHAT_COMPLETIONS_URL,
    PollinationsSuggestionsProvider,
    SuggestionsProviderError,
    SuggestionsProviderUnavailable,
)


VALID_SUGGESTIONS = {
    "pose_suggestions": ["Pose one", "Pose two", "Pose three"],
    "camera_angles": ["Angle one", "Angle two", "Angle three"],
    "lighting_tips": ["Light one", "Light two", "Light three"],
    "camera_settings": ["Setting one", "Setting two", "Setting three"],
    "composition_tips": ["Composition one", "Composition two", "Composition three"],
    "photography_tools": ["Tool one", "Tool two", "Tool three"],
}


class PollinationsSuggestionsProviderTests(unittest.TestCase):
    def setUp(self):
        self.api_key = "test-key-not-a-real-credential"
        self.settings = SimpleNamespace(
            pollinations_api_key=self.api_key,
            pollinations_chat_model="openai/gpt-5.4-nano",
            pollinations_chat_timeout_seconds=45,
            pollinations_enabled=False,
        )
        self.settings_patch = patch(
            "app.services.suggestions_provider.settings", self.settings
        )
        self.settings_patch.start()

    def tearDown(self):
        self.settings_patch.stop()

    def test_sends_documented_chat_request_and_validates_six_categories(self):
        prompt = "Plan details: outdoor portrait with one person."
        captured = {}

        def responder(request):
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers.get("authorization")
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": json.dumps(VALID_SUGGESTIONS)}}
                    ]
                },
            )

        provider = PollinationsSuggestionsProvider(httpx.MockTransport(responder))
        suggestions = asyncio.run(provider.generate(prompt))

        self.assertEqual(captured["url"], POLLINATIONS_CHAT_COMPLETIONS_URL)
        self.assertEqual(captured["authorization"], f"Bearer {self.api_key}")
        self.assertEqual(captured["body"]["model"], "openai/gpt-5.4-nano")
        self.assertEqual(captured["body"]["max_tokens"], 1200)
        self.assertEqual(
            captured["body"]["messages"][-1],
            {"role": "user", "content": prompt},
        )
        self.assertEqual(suggestions.model_dump(), VALID_SUGGESTIONS)
        self.assertFalse(self.settings.pollinations_enabled)

    def test_rejects_malformed_or_incomplete_provider_responses(self):
        malformed_contents = (
            "not JSON",
            json.dumps({**VALID_SUGGESTIONS, "camera_angles": ["Only one"]}),
            json.dumps({**VALID_SUGGESTIONS, "unexpected": ["extra"]}),
        )
        for content in malformed_contents:
            with self.subTest(content=content):
                provider = PollinationsSuggestionsProvider(
                    httpx.MockTransport(
                        lambda request: httpx.Response(
                            200,
                            json={"choices": [{"message": {"content": content}}]},
                        )
                    )
                )
                with self.assertRaises(SuggestionsProviderError):
                    asyncio.run(provider.generate("Plan details"))

    def test_provider_http_failures_are_generic_and_do_not_log_credentials(self):
        provider = PollinationsSuggestionsProvider(
            httpx.MockTransport(lambda request: httpx.Response(429))
        )
        with self.assertLogs("app.services.suggestions_provider", level=logging.WARNING) as logs:
            with self.assertRaises(SuggestionsProviderError):
                asyncio.run(provider.generate("Plan details"))
        self.assertIn("status_code=429", logs.output[0])
        self.assertNotIn(self.api_key, "\n".join(logs.output))

    def test_transport_failures_are_sanitized(self):
        def fail_request(request):
            raise httpx.ConnectError("transport failure with no credential data")

        provider = PollinationsSuggestionsProvider(httpx.MockTransport(fail_request))
        with self.assertLogs("app.services.suggestions_provider", level=logging.WARNING) as logs:
            with self.assertRaises(SuggestionsProviderError):
                asyncio.run(provider.generate("Plan details"))
        self.assertIn("stage=transport", logs.output[0])
        self.assertNotIn(self.api_key, "\n".join(logs.output))

    def test_missing_api_key_disables_suggestions_without_http_request(self):
        self.settings.pollinations_api_key = ""
        provider = PollinationsSuggestionsProvider(
            httpx.MockTransport(
                lambda request: self.fail("HTTP request must not be sent")
            )
        )
        with self.assertRaises(SuggestionsProviderUnavailable):
            asyncio.run(provider.generate("Plan details"))


if __name__ == "__main__":
    unittest.main()
