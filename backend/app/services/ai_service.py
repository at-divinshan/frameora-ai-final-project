"""Four-image requests on the existing account allowance and private media schema."""

import logging
import json
from datetime import datetime, timezone
import time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_generation import AIGeneration
from app.models.ai_result import AIResult
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.repositories.user_repository import lock_profile
from app.repositories import plan_repository
from app.services.generation_planning import build_image_prompt, planned_shots
from app.schemas.ai import ImageGuidance
from pydantic import ValidationError
from app.services import ai_image_storage as storage
from app.services import free_generation_service as allowance
from app.services import pollinations_service as provider

logger = logging.getLogger(__name__)
ASSET_TYPE = "ai_generated"


def generation_view(db: Session, generation: AIGeneration) -> dict:
    assets = []
    if generation.status == allowance.SUCCESS_STATUS:
        assets = db.scalars(select(MediaAsset).where(
            MediaAsset.generation_id == generation.id,
            MediaAsset.user_id == generation.user_id,
            MediaAsset.asset_type == ASSET_TYPE,
        ).order_by(MediaAsset.id)).all()
    # Historical generations have no structured guidance. Never invent it on read.
    guidance = {}
    try:
        saved = json.loads(generation.guidance_text or "null")
        if isinstance(saved, dict) and saved.get("version") == 1 and isinstance(saved.get("images"), dict):
            for asset_id, value in saved["images"].items():
                try:
                    guidance[asset_id] = ImageGuidance.model_validate(value).model_dump()
                except ValidationError:
                    continue
    except (ValueError, TypeError):
        pass
    return {
        "id": generation.id, "plan_id": generation.plan_id,
        "status": generation.status, "created_at": generation.created_at,
        "images": [{"id": asset.id, "url": f"/ai/images/{asset.id}",
                    "guidance": guidance.get(str(asset.id))} for asset in assets],
    }


def list_generations(db: Session, user: User, *, before: int | None = None) -> list[dict]:
    query = select(AIGeneration).where(AIGeneration.user_id == user.id)
    if before is not None:
        query = query.where(AIGeneration.id < before)
    return [generation_view(db, item) for item in db.scalars(
        query.order_by(AIGeneration.id.desc()).limit(20)
    )]


def generate(db: Session, user: User, *, plan_id: int, description: str, reference: bytes | None):
    provider.require_configured()
    plan = plan_repository.find_for_user(db, user.id, plan_id)
    if plan is None:
        raise HTTPException(404, "Photography plan not found.")
    prompt = build_image_prompt(plan, description)
    shots = planned_shots(plan)
    # Reconcile terminal work left by a lost finalization acknowledgement. Pending
    # work is never expired or released based on age alone.
    allowance.reconcile_interrupted_request(db, user_id=user.id)
    reservation = allowance.reserve_free_request(db, user, plan_id=plan_id, quality="standard")
    keys = []
    persistence_started = False
    stage = "provider"
    generation_started = time.monotonic()
    try:
        # Do not retain a DB transaction across network calls.
        images = provider.generate_images(prompt, reference, shots=shots)
        if len(images) != 4 or len(set(images)) != 4:
            raise HTTPException(502, "The provider did not return four different images.")
        stage = "storage"
        for data in images:
            storage_started = time.monotonic()
            try:
                keys.append(storage.write_image(data))
            except OSError as error:
                logger.warning(
                    "AI image diagnostic stage=storage_error http_status=none "
                    "exception_category=%s validation_stage=not_applicable elapsed_ms=%d",
                    type(error).__name__,
                    max(0, round((time.monotonic() - storage_started) * 1000)),
                )
                raise
        # Follow the allowance service's lock order. Completion below commits both
        # the result set and allowance in the same transaction.
        stage = "database_finalization"
        lock_profile(db, user.id)
        generation = db.get(AIGeneration, reservation.generation_id)
        if generation is None or generation.status != allowance.PENDING_STATUS:
            raise HTTPException(409, "The generation is no longer active.")
        saved_guidance = {}
        for key, shot in zip(keys, shots):
            db.add(AIResult(generation_id=generation.id))
            asset = MediaAsset(user_id=user.id, plan_id=plan_id, generation_id=generation.id,
                               asset_type=ASSET_TYPE, file_url=key)
            db.add(asset)
            db.flush()
            saved_guidance[str(asset.id)] = shot
        generation.guidance_text = json.dumps({"version": 1, "images": saved_guidance}, ensure_ascii=False)
        generation.model_name = settings.pollinations_image_model
        generation.status = allowance.SUCCESS_STATUS
        generation.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.flush()  # SessionLocal disables autoflush; completion must see all rows.
        persistence_started = True
        allowance.complete_free_request(db, user, reservation=reservation)
        return generation_view(db, generation)
    except Exception as error:
        if stage == "database_finalization" and not persistence_started:
            logger.warning(
                "AI image diagnostic stage=database_finalization_error http_status=none "
                "exception_category=%s validation_stage=not_applicable elapsed_ms=%d",
                type(error).__name__,
                max(0, round((time.monotonic() - generation_started) * 1000)),
            )
        db.rollback()
        if not persistence_started:
            for key in keys:
                try:
                    storage.delete_image(key)
                except OSError:
                    logger.warning("Private AI image cleanup deferred.")
            allowance.release_failed_request(db, user, reservation=reservation)
        else:
            # A lost COMMIT acknowledgement can mean success. Keep immutable files
            # and the claim; never release it or delete potentially committed media.
            logger.warning(
                "AI image diagnostic stage=database_finalization_unconfirmed "
                "http_status=none exception_category=%s validation_stage=commit elapsed_ms=%d",
                type(error).__name__,
                max(0, round((time.monotonic() - generation_started) * 1000)),
            )
        if persistence_started:
            raise HTTPException(503, "Generation finalization could not be confirmed. Check your gallery before trying again.") from None
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(503, "Generation could not be saved. Your free request has not been used.") from None


def get_image(db: Session, user: User, asset_id: int) -> bytes:
    asset = db.scalar(select(MediaAsset).join(
        AIGeneration, AIGeneration.id == MediaAsset.generation_id
    ).where(MediaAsset.id == asset_id, MediaAsset.user_id == user.id,
            AIGeneration.user_id == user.id, AIGeneration.status == allowance.SUCCESS_STATUS,
            MediaAsset.asset_type == ASSET_TYPE))
    if asset is None:
        raise HTTPException(404, "Image not found.")
    try:
        return storage.read_image(asset.file_url)
    except OSError:
        raise HTTPException(404, "Image not found.") from None
