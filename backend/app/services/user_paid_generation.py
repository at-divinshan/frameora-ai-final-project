"""Normal User four-credit batches. User locks serialize the existing credit ledger."""
from dataclasses import dataclass
from hashlib import sha256
import json

from fastapi import HTTPException
from sqlalchemy import select
from app.models.ai_generation import AIGeneration
from app.models.credit_transaction import CreditTransaction
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.user_repository import lock_profile
from app.services import paid_credit_service
from app.services.subscription_service import clock

COST = 4
PENDING = 'user_paid_reserved'

@dataclass(frozen=True)
class Reservation:
    generation_id: int
    replay: bool = False


def _lock(db, user):
    current = lock_profile(db, user.id)
    if current is None or current.role != 'user':
        raise HTTPException(403, 'Normal User access required.')


def reserve(db, user, *, plan_id, prompt, reference, background_reference, idempotency_key):
    if user.role != 'user':
        raise HTTPException(403, 'Normal User access required.')
    try:
        _lock(db, user)
        digest = sha256(json.dumps([plan_id, prompt,
            sha256(reference or b'').hexdigest(), sha256(background_reference or b'').hexdigest()],
            separators=(',', ':')).encode()).digest()
        key = sha256(('user-paid:v1:' + (idempotency_key or '')).encode()).digest()
        previous = db.scalar(select(CreditTransaction).where(
            CreditTransaction.user_id == user.id, CreditTransaction.operation_key == key)) if idempotency_key else None
        if previous is not None:
            if previous.request_hash != digest or previous.transaction_type != 'spend' or previous.credits_change != -COST:
                raise HTTPException(409, 'Retry key does not match this request.')
            generation = db.get(AIGeneration, previous.generation_id)
            if generation is None or generation.user_id != user.id:
                raise HTTPException(503, 'Generation reservation requires review.')
            if generation.status != 'completed':
                raise HTTPException(409, 'This request is pending or failed. Check your gallery; use a new key only after confirmed failure.')
            result = Reservation(generation.id, True)
            db.rollback()
            return result
        rows = list(db.scalars(select(Subscription).where(
            Subscription.user_id == user.id, Subscription.status == 'active').with_for_update()))
        if len(rows) > 1:
            raise HTTPException(503, 'Subscription state requires review.')
        sub = rows[0] if rows else None
        now = clock()
        if sub is None or (sub.end_date is not None and sub.end_date <= now):
            db.rollback()
            return None  # Existing free history remains authoritative.
        if sub.plan_kind not in ('starter', 'pro'):
            raise HTTPException(503, 'Normal User paid subscription requires review.')
        if not idempotency_key or not 16 <= len(idempotency_key) <= 128:
            raise HTTPException(422, 'A stable request key is required for paid generation.')
        remaining, start, end = paid_credit_service.balance(db, sub, now)
        if remaining < COST:
            raise HTTPException(402, 'Four credits are required for this generation.')
        generation = AIGeneration(user_id=user.id, plan_id=plan_id, quality='standard',
                                  status=PENDING, created_at=now)
        db.add(generation)
        db.flush()
        db.add(CreditTransaction(user_id=user.id, generation_id=generation.id,
            subscription_id=sub.id, period_start=start, period_end=end,
            credits_change=-COST, transaction_type='spend', created_at=now,
            operation_key=key, request_hash=digest))
        result = Reservation(generation.id)
        db.commit()  # An uncertain reservation never starts provider work.
        return result
    except Exception:
        db.rollback()
        raise


def _debit(db, user, reservation):
    debit = db.scalar(select(CreditTransaction).where(
        CreditTransaction.user_id == user.id,
        CreditTransaction.generation_id == reservation.generation_id,
        CreditTransaction.transaction_type == 'spend'))
    if debit is None or debit.credits_change != -COST:
        raise HTTPException(503, 'Original credit reservation requires review.')
    return debit


def settle(db, user, reservation):
    debit = _debit(db, user, reservation)
    sub = db.get(Subscription, debit.subscription_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(503, 'Original subscription is unavailable.')
    paid_credit_service.proof(db, sub, clock(), settlement=True)


def fail(db, user, reservation):
    """Only called after confirmed pre-commit failure, never by timeout/replay."""
    try:
        # Recovery is internal and must still refund if the account was disabled
        # during the provider call. It grants no access or new spending authority.
        current = db.get(User, user.id, populate_existing=True, with_for_update=True)
        if current is None:
            raise HTTPException(503, "Credit recovery account is unavailable.")
        generation = db.get(AIGeneration, reservation.generation_id)
        if generation is None or generation.user_id != user.id or generation.status != PENDING:
            db.rollback()
            return
        debit = _debit(db, user, reservation)
        key = sha256(f'user-paid-refund:v1:{generation.id}'.encode()).digest()
        existing = db.scalar(select(CreditTransaction).where(
            CreditTransaction.user_id == user.id, CreditTransaction.operation_key == key))
        if existing is not None:
            raise HTTPException(503, 'Credit recovery requires review.')
        db.add(CreditTransaction(user_id=user.id, generation_id=generation.id,
            subscription_id=debit.subscription_id, period_start=debit.period_start,
            period_end=debit.period_end, credits_change=COST, transaction_type='refund',
            created_at=clock(), operation_key=key, request_hash=debit.request_hash))
        generation.status = 'failed'
        generation.completed_at = clock()
        db.commit()
    except Exception:
        db.rollback()
        raise
