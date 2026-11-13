"""Configurable owner batches with durable idempotency and fenced timeout recovery.

An existing spend row records the original batch cost. Completion keeps it; failure adds
one matching refund to its ORIGINAL period. No locks span provider/file work.
"""

from datetime import timedelta
from hashlib import sha256
import json
import logging
import time

from fastapi import HTTPException
from sqlalchemy import select, func

from app.core.config import settings
from app.models.ai_generation import AIGeneration
from app.models.ai_result import AIResult
from app.models.credit_transaction import CreditTransaction
from app.models.media_asset import MediaAsset
from app.models.photography_plan import PhotographyPlan
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories import plan_repository
from app.repositories.user_repository import lock_profile
from app.services import ai_image_storage as storage, ai_service, pollinations_service as provider
from app.services import owner_entitlement_service as entitlements, subscription_service as subscriptions
from app.schemas.owner_ai import OwnerGenerationPreferences
from app.services.generation_planning import build_owner_image_prompt, planned_owner_shots
from app.services.onboarding_service import require_owner
from app.services import project_service

logger = logging.getLogger(__name__)
PENDING = 'owner_reserved'
SUCCESS = 'completed'
FAILED = 'failed'
RECOVERY_AFTER = timedelta(minutes=45)  # Above eight configured calls (max 8 x 300s).
MAX_RECOVERY_BATCH = 50
LEGACY_BATCH_COST = 4
DEFAULT_PREFERENCES = OwnerGenerationPreferences().model_dump()


def operation_key(key):
    return sha256(('owner-generation:v1:' + key).encode()).digest()


def request_hash(plan_id, description, reference, project_id=None, preferences=None, background_reference=None):
    # A saved plan may change after submission. A retry is identified by the submitted
    # inputs, not the subsequently edited plan; its original results are immutable.
    value = [plan_id, description.strip(), sha256(reference).hexdigest() if reference is not None else None]
    if background_reference is not None:
        value.append({"background_reference": sha256(background_reference).hexdigest()})
    if project_id is not None:
        value.append(project_id)
    if preferences and preferences != DEFAULT_PREFERENCES:
        value.append(preferences)
    return sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).digest()


def _log_generation_diagnostic(stage, generation_id, started, *, error=None, http_status=None,
                               image_index=None, level=logging.WARNING):
    logger.log(
        level,
        'Owner generation diagnostic generation_id=%s image_index=%s stage=%s '
        'http_status=%s exception_category=%s elapsed_ms=%d',
        generation_id,
        image_index if image_index is not None else 'none',
        stage,
        http_status if http_status is not None else 'none',
        type(error).__name__ if error is not None else 'none',
        max(0, round((time.monotonic() - started) * 1000)),
    )


def _lock_owner(db, user):
    require_owner(lock_profile(db, user.id))


def _owned(db, user_id, generation_id):
    row = db.execute(select(AIGeneration, CreditTransaction).join(
        CreditTransaction, CreditTransaction.generation_id == AIGeneration.id
    ).where(AIGeneration.id == generation_id, AIGeneration.user_id == user_id,
        CreditTransaction.user_id == user_id, CreditTransaction.transaction_type == 'spend')
        .execution_options(populate_existing=True).with_for_update()).one_or_none()
    if row is None:
        raise HTTPException(403, 'You do not have access to this generation.')
    generation, debit = row
    if generation.status not in (PENDING, SUCCESS, FAILED):
        raise HTTPException(503, 'Generation state requires review.')
    subscription = db.get(Subscription, debit.subscription_id)
    if (subscription is None or subscription.user_id != user_id
            or debit.credits_change not in (-2, -LEGACY_BATCH_COST, -8)):
        raise HTTPException(503, 'Generation accounting requires review.')
    return generation, debit


def _refund_locked(db, generation, debit, now):
    if generation.status != PENDING:
        return generation.status == FAILED
    key = sha256(f'owner-refund:v1:{generation.id}'.encode()).digest()
    refund = db.scalar(select(CreditTransaction).where(
        CreditTransaction.user_id == generation.user_id, CreditTransaction.operation_key == key))
    if refund is None:
        db.add(CreditTransaction(user_id=generation.user_id, generation_id=generation.id,
            subscription_id=debit.subscription_id, credits_change=-debit.credits_change,
            transaction_type='refund', created_at=now, period_start=debit.period_start,
            period_end=debit.period_end, operation_key=key, request_hash=debit.request_hash))
    elif (refund.generation_id != generation.id or refund.subscription_id != debit.subscription_id
          or refund.credits_change != -debit.credits_change or refund.transaction_type != 'refund'
          or refund.period_start != debit.period_start or refund.period_end != debit.period_end
          or refund.request_hash != debit.request_hash):
        raise HTTPException(503, 'Generation accounting requires review.')
    generation.status = FAILED  # Durable fence: a late worker cannot settle successfully.
    generation.completed_at = now
    generation.error_message = 'Batch failed or its recovery deadline elapsed.'
    db.flush()
    return True


def _recover_expired_locked(db, user, now):
    ids = list(db.scalars(select(AIGeneration.id).where(
        AIGeneration.user_id == user.id, AIGeneration.status == PENDING,
        AIGeneration.created_at <= now - RECOVERY_AFTER).order_by(AIGeneration.id)
        .limit(MAX_RECOVERY_BATCH)))
    for generation_id in ids:
        generation, debit = _owned(db, user.id, generation_id)
        _refund_locked(db, generation, debit, now)


def _reserve(db, user, plan_id, description, reference, key, project_id=None, preferences=None, background_reference=None):
    try:
        _lock_owner(db, user)
        now = subscriptions.clock()
        preferences = OwnerGenerationPreferences.model_validate(
            preferences or DEFAULT_PREFERENCES
        ).model_dump()
        digest = request_hash(plan_id, description, reference, project_id, preferences, background_reference)
        plan = None
        if project_id is not None:
            project_service.require_project_access(db, user, project_id, editable=False)
            plan = plan_repository.find_for_user(db, user.id, plan_id)
            if plan is None or plan.project_id != project_id:
                raise HTTPException(404, 'Photography plan not found for this project.')
        existing = db.scalar(select(CreditTransaction).where(
            CreditTransaction.user_id == user.id, CreditTransaction.operation_key == operation_key(key))
            .execution_options(populate_existing=True).with_for_update())
        if existing is not None:
            if existing.request_hash != digest or existing.transaction_type != 'spend':
                raise HTTPException(409, 'Idempotency key was already used with different inputs.')
            generation, debit = _owned(db, user.id, existing.generation_id)
            if generation.status == PENDING and now >= generation.created_at + RECOVERY_AFTER:
                _refund_locked(db, generation, debit, now)
            generation_id = generation.id
            db.commit()
            return generation_id, None, None
        if project_id is not None:
            project_service.require_project_access(db, user, project_id, editable=True)
        if plan is None:
            plan = plan_repository.find_for_user(db, user.id, plan_id)
        if plan is None:
            raise HTTPException(403, 'You do not have access to this photography plan.')
        prompt = build_owner_image_prompt(plan, description, preferences, **({"background_reference": True, "person_reference": reference is not None} if background_reference is not None else {}))
        shots = planned_owner_shots(plan, preferences, background_reference=background_reference is not None)
        _recover_expired_locked(db, user, now)
        subscription, state = entitlements.resolve_locked(db, user, now=now, persist=True, grant=True)
        if not state['generation_allowed']:
            # Commit only the safe expiry/recovery/grant work, never a debit.
            db.commit()
            code = 402 if state['reason'] == 'insufficient_credits' else 409
            raise HTTPException(code, state['reason'])
        provider.require_configured()  # Replay/recovery never requires a working provider.
        generation = AIGeneration(user_id=user.id, plan_id=plan.id, quality='standard',
            status=PENDING, created_at=now, model_name=settings.pollinations_image_model)
        db.add(generation)
        db.flush()
        db.add(CreditTransaction(user_id=user.id, subscription_id=subscription.id,
            generation_id=generation.id, credits_change=-entitlements.BATCH_COST,
            transaction_type='spend', created_at=now, period_start=state['period_start'],
            period_end=state['period_end'], operation_key=operation_key(key), request_hash=digest))
        db.flush()
        generation_id = generation.id
        db.commit()  # No provider call until the reservation commit is acknowledged.
        return generation_id, prompt, shots
    except Exception:
        db.rollback()
        raise


def _fail(db, user, generation_id):
    started = time.monotonic()
    try:
        # Internal compensation returns only an already-reserved debit to its
        # original period. It must still work if this worker's login was revoked
        # or the account's role changed while the provider was running.
        if db.get(User, user.id, populate_existing=True, with_for_update=True) is None:
            raise HTTPException(503, 'Generation accounting requires review.')
        generation, debit = _owned(db, user.id, generation_id)
        failed = _refund_locked(db, generation, debit, subscriptions.clock())
        db.commit()
        if failed:
            _log_generation_diagnostic(
                'credit_refund_completed', generation_id, started, level=logging.INFO
            )
        return failed
    except Exception as error:
        db.rollback()
        _log_generation_diagnostic(
            'credit_refund_error',
            generation_id,
            started,
            error=error,
            http_status=error.status_code if isinstance(error, HTTPException) else None,
        )
        raise


def _response_locked(db, user, generation, debit=None, *, replayed=False):
    if debit is None:
        debit = db.scalar(select(CreditTransaction).where(
            CreditTransaction.generation_id == generation.id,
            CreditTransaction.user_id == user.id,
            CreditTransaction.transaction_type == 'spend',
        ))
    if debit is None:
        raise HTTPException(503, 'Generation accounting requires review.')
    batch_cost = -debit.credits_change
    result = ai_service.generation_view(db, generation)
    if generation.status == SUCCESS and len(result['images']) != batch_cost:
        raise HTTPException(503, 'Saved generation requires review; no automatic refund was issued.')
    for image in result['images']:
        image['url'] = f"/owner/ai/images/{image['id']}"
    _, state = entitlements.resolve_locked(db, user, now=subscriptions.clock())
    result.update(remaining_credits=state['remaining_credits'],
        reserved_credits=batch_cost if generation.status == PENDING else 0,
        charged_credits=batch_cost if generation.status == SUCCESS else 0,
        recover_after=generation.created_at + RECOVERY_AFTER if generation.status == PENDING else None,
        replayed=replayed)
    return result


def get_result(db, user, generation_id, *, replayed=False):
    try:
        _lock_owner(db, user)
        generation, debit = _owned(db, user.id, generation_id)
        return _response_locked(db, user, generation, debit, replayed=replayed)
    finally:
        db.rollback()


def recover(db, user, generation_id):
    try:
        _lock_owner(db, user)
        generation, debit = _owned(db, user.id, generation_id)
        now = subscriptions.clock()
        if generation.status == PENDING:
            if now < generation.created_at + RECOVERY_AFTER:
                raise HTTPException(409, 'Generation is still in progress. Recovery is available after 30 minutes.')
            _refund_locked(db, generation, debit, now)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_result(db, user, generation_id)


def generate(db, user, *, plan_id, description, reference, idempotency_key,
             project_id=None, preferences=None, background_reference=None):
    provider.require_reference_support(background_reference)
    generation_id, prompt, shots = _reserve(
        db, user, plan_id, description, reference, idempotency_key, project_id, preferences, background_reference
    )
    if prompt is None:
        result = get_result(db, user, generation_id, replayed=True)
        if result['status'] == PENDING:
            raise HTTPException(409, {'message': 'Generation is already in progress.',
                                     'generation_id': generation_id, 'status': PENDING})
        return result  # Failed keys stay terminal; an intentional new attempt needs a new key.
    keys = []
    commit_attempted = False
    generation_started = time.monotonic()
    stage = 'provider_request'
    try:
        images = provider.generate_images(
            prompt, reference, shots=shots, generation_id=generation_id,
            **({"background_reference": background_reference} if background_reference is not None else {})
        )
        stage = 'image_validation'
        if len(images) != len(shots) or len(set(images)) != len(shots):
            _log_generation_diagnostic(
                'image_validation_error', generation_id, generation_started,
                error=ValueError('Incomplete batch'),
            )
            raise ValueError('Incomplete batch')
        stage = 'storage'
        for image_index, data in enumerate(images, start=1):
            try:
                keys.append(storage.write_image(data))
            except Exception as error:
                _log_generation_diagnostic(
                    'storage_error',
                    generation_id,
                    generation_started,
                    error=error,
                    image_index=image_index,
                )
                raise
        stage = 'credit_settlement'
        _lock_owner(db, user)
        generation, debit = _owned(db, user.id, generation_id)
        if generation.status != PENDING:
            raise HTTPException(409, 'This generation is no longer active.')
        if subscriptions.clock() >= generation.created_at + RECOVERY_AFTER:
            raise HTTPException(409, 'Generation recovery deadline elapsed.')
        # Ownership and the original debit are rechecked above. Do not move this
        # charge to a newer subscription or period if expiry occurred during work.
        if db.scalar(select(func.count()).select_from(MediaAsset).where(MediaAsset.generation_id == generation.id)):
            raise HTTPException(503, 'Generation storage requires review.')
        guidance = {}
        for key, shot in zip(keys, shots):
            asset = MediaAsset(user_id=user.id, plan_id=generation.plan_id,
                generation_id=generation.id, asset_type=ai_service.ASSET_TYPE, file_url=key)
            db.add(asset)
            db.add(AIResult(generation_id=generation.id))
            db.flush()
            guidance[str(asset.id)] = shot
        generation.guidance_text = json.dumps({'version': 1, 'images': guidance}, ensure_ascii=False)
        generation.status = SUCCESS
        generation.completed_at = subscriptions.clock()
        from app.services.project_phase_service import record_completed
        record_completed(db, generation, generation.completed_at)
        db.flush()
        from app.services import notification_service
        if notification_service.available(db):
            _, notification_state = entitlements.resolve_locked(db, user, now=subscriptions.clock())
            notification_service.owner_state(db, user, notification_state)
        commit_attempted = True
        db.commit()  # All batch rows, metadata and success status become visible together.
        _log_generation_diagnostic(
            'credit_settlement_completed',
            generation_id,
            generation_started,
            level=logging.INFO,
        )
    except Exception as error:
        diagnostic_stage = stage
        if stage == 'provider_request':
            diagnostic_stage = 'provider_error'
        elif stage == 'image_validation':
            diagnostic_stage = 'image_validation_error'
        elif stage == 'credit_settlement':
            diagnostic_stage = (
                'credit_settlement_unconfirmed' if commit_attempted else 'credit_settlement_error'
            )
        _log_generation_diagnostic(
            diagnostic_stage,
            generation_id,
            generation_started,
            error=error,
            http_status=error.status_code if isinstance(error, HTTPException) else None,
        )
        db.rollback()
        if not commit_attempted:
            try:
                failed = _fail(db, user, generation_id)
            except Exception:
                failed = False  # Uncertain refund commit: retain files and recover by ID/key.
                logger.warning(
                    'Owner generation recovery diagnostic generation_id=%s stage=credit_refund_unconfirmed',
                    generation_id,
                )
            if failed:
                for key in keys:
                    try:
                        storage.delete_image(key)
                    except OSError:
                        logger.warning(
                            'Owner generation diagnostic generation_id=%s stage=storage_cleanup_deferred',
                            generation_id,
                        )
        # After an uncertain completion commit, never refund or delete files here.
        raise HTTPException(503, {'message': 'Generation could not be confirmed. Check its status before retrying.',
                                 'generation_id': generation_id}) from None
    return get_result(db, user, generation_id)


def list_results(db, user):
    try:
        _lock_owner(db, user)
        ids = list(db.scalars(select(AIGeneration.id).join(CreditTransaction,
            CreditTransaction.generation_id == AIGeneration.id).where(
            AIGeneration.user_id == user.id, CreditTransaction.user_id == user.id,
            CreditTransaction.transaction_type == 'spend').order_by(AIGeneration.id.desc()).limit(20)))
        return [_response_locked(db, user, *_owned(db, user.id, gid)) for gid in ids]
    finally:
        db.rollback()


def list_project_results(db, user, project_id, before=None):
    try:
        _lock_owner(db, user)
        project_service.require_project_access(db, user, project_id, editable=False)
        ids = list(db.scalars(select(AIGeneration.id)
            .join(CreditTransaction, CreditTransaction.generation_id == AIGeneration.id)
            .join(PhotographyPlan, PhotographyPlan.id == AIGeneration.plan_id)
            .where(AIGeneration.user_id == user.id, CreditTransaction.user_id == user.id,
                CreditTransaction.transaction_type == 'spend',
                PhotographyPlan.user_id == user.id, PhotographyPlan.project_id == project_id,
                AIGeneration.id < before if before is not None else True)
            .order_by(AIGeneration.id.desc()).limit(20)))
        return [_response_locked(db, user, *_owned(db, user.id, gid)) for gid in ids]
    finally:
        db.rollback()


def get_image(db, user, asset_id):
    # Existing private-image retrieval verifies generation/user ownership and success.
    require_owner(user)
    return ai_service.get_image(db, user, asset_id)
