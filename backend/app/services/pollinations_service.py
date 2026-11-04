"""Pollinations OpenAPI image contract. Never return provider payloads to clients."""

import base64
import binascii
import json
import logging
import time

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.services import ai_image_storage as storage

logger = logging.getLogger(__name__)
BASE_URL = "https://gen.pollinations.ai"
POSES = (
    "Standing, relaxed shoulders, full-body composition, eye-level camera.",
    "Seated, hands resting naturally, three-quarter angle, medium portrait.",
    "Walking naturally, looking toward camera, wide environmental composition.",
    "Looking over one shoulder, close portrait, slightly elevated camera.",
)


def _log_diagnostic(
    *,
    stage: str,
    elapsed_ms: int,
    http_status: int | None = None,
    exception_category: str = "none",
    validation_stage: str = "not_applicable",
    level: int = logging.WARNING,
) -> None:
    logger.log(
        level,
        "Pollinations image diagnostic stage=%s http_status=%s exception_category=%s "
        "validation_stage=%s elapsed_ms=%d",
        stage,
        http_status if http_status is not None else "none",
        exception_category,
        validation_stage,
        elapsed_ms,
    )


def require_configured():
    if not settings.pollinations_enabled or not settings.pollinations_api_key:
        raise HTTPException(503, "AI generation is not configured yet. Please try again later.")


def generate_images(description: str, reference: bytes | None) -> list[bytes]:
    require_configured()
    identity = (
        "Create a photographic portrait of the same person throughout this series. "
        "Keep facial features, skin tone, hair and apparent age consistent. "
        "Use the reference person's appearance when an image is supplied. "
        "Produce one photograph, not a collage. Subject and setting: " + description
    )
    images = []
    elapsed_started = time.monotonic()
    last_http_status = None
    transport = httpx.HTTPTransport()
    try:
        with httpx.Client(transport=transport, timeout=httpx.Timeout(
            settings.pollinations_timeout_seconds, connect=10
        ), follow_redirects=False, trust_env=False) as client:
            for pose in POSES:
                body = {
                    "model": settings.pollinations_image_model,
                    "prompt": identity + "\nPose and composition: " + pose,
                    "response_format": "b64_json",
                    "n": 1,
                }
                endpoint = "/v1/images/generations"
                if reference is not None:
                    endpoint = "/v1/images/edits"
                    body["image"] = [{"image_url": "data:image/png;base64," + base64.b64encode(reference).decode("ascii")}]
                call_started = time.monotonic()
                validation_stage = "http_response"
                try:
                    with client.stream(
                        "POST",
                        BASE_URL + endpoint,
                        json=body,
                        headers={"Authorization": "Bearer " + settings.pollinations_api_key},
                    ) as response:
                        last_http_status = response.status_code
                        if response.status_code != 200:
                            _log_diagnostic(
                                stage="provider_http_error",
                                http_status=response.status_code,
                                exception_category="HTTPStatusError",
                                elapsed_ms=_elapsed_ms(call_started),
                            )
                            raise ValueError("Provider rejected request")
                        validation_stage = "response_size"
                        payload = bytearray()
                        for chunk in response.iter_bytes():
                            payload.extend(chunk)
                            if (
                                len(payload) > 18 * 1024 * 1024
                                or time.monotonic() - call_started
                                > settings.pollinations_timeout_seconds
                            ):
                                raise ValueError("Provider response limit")
                    validation_stage = "response_json"
                    data = json.loads(payload)
                except httpx.TimeoutException as error:
                    _log_diagnostic(
                        stage="timeout",
                        http_status=last_http_status,
                        exception_category=type(error).__name__,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise
                except httpx.ConnectError as error:
                    _log_diagnostic(
                        stage="connection_error",
                        http_status=last_http_status,
                        exception_category=type(error).__name__,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise
                except httpx.HTTPError as error:
                    _log_diagnostic(
                        stage="provider_transport_error",
                        http_status=last_http_status,
                        exception_category=type(error).__name__,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise
                except json.JSONDecodeError as error:
                    _log_diagnostic(
                        stage="invalid_json",
                        http_status=last_http_status,
                        exception_category=type(error).__name__,
                        validation_stage=validation_stage,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise
                except UnicodeDecodeError as error:
                    _log_diagnostic(
                        stage="invalid_json",
                        http_status=last_http_status,
                        exception_category=type(error).__name__,
                        validation_stage=validation_stage,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise
                except ValueError as error:
                    if validation_stage == "response_size":
                        _log_diagnostic(
                            stage="response_validation_error",
                            http_status=last_http_status,
                            exception_category=type(error).__name__,
                            validation_stage=validation_stage,
                            elapsed_ms=_elapsed_ms(call_started),
                        )
                    raise

                validation_stage = "response_shape"
                if not isinstance(data, dict):
                    _log_diagnostic(
                        stage="response_validation_error",
                        http_status=last_http_status,
                        exception_category="TypeError",
                        validation_stage=validation_stage,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise TypeError("Provider response must be an object")
                data = data.get("data")
                if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
                    _log_diagnostic(
                        stage="response_validation_error",
                        http_status=last_http_status,
                        exception_category="ValueError",
                        validation_stage=validation_stage,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise ValueError("Incomplete provider response")
                encoded_image = data[0].get("b64_json")
                if not isinstance(encoded_image, str):
                    _log_diagnostic(
                        stage="response_validation_error",
                        http_status=last_http_status,
                        exception_category="TypeError",
                        validation_stage="base64_field",
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise TypeError("Image payload must be encoded text")

                validation_stage = "base64_decode"
                try:
                    raw = base64.b64decode(encoded_image, validate=True)
                except (binascii.Error, ValueError) as error:
                    _log_diagnostic(
                        stage="invalid_base64",
                        http_status=last_http_status,
                        exception_category=type(error).__name__,
                        validation_stage=validation_stage,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise

                validation_stage = "image_validation"
                try:
                    image = storage.normalize_image(raw)
                except HTTPException as error:
                    _log_diagnostic(
                        stage="image_validation_error",
                        http_status=last_http_status,
                        exception_category=type(error).__name__,
                        validation_stage=validation_stage,
                        elapsed_ms=_elapsed_ms(call_started),
                    )
                    raise
                images.append(image)
                _log_diagnostic(
                    stage="completed",
                    http_status=last_http_status,
                    validation_stage="passed",
                    elapsed_ms=_elapsed_ms(call_started),
                    level=logging.INFO,
                )
        if len(set(images)) != len(POSES):
            _log_diagnostic(
                stage="duplicate_images",
                http_status=last_http_status,
                exception_category="ValueError",
                validation_stage="distinct_image_check",
                elapsed_ms=_elapsed_ms(elapsed_started),
            )
            raise ValueError("Duplicate provider images")
        return images
    except (httpx.HTTPError, ValueError, KeyError, TypeError, binascii.Error, HTTPException):
        raise HTTPException(502, "Image generation could not finish. Your free request has not been used.") from None


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
