"""Account-scoped free generation reservation foundation; no provider calls."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import secrets

from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.ai_generation import AIGeneration
from app.models.free_generation_allowance import FreeGenerationAllowance
from app.models.photography_plan import PhotographyPlan
from app.models.user import User
from app.repositories.user_repository import lock_profile

SCHEMA_UNAVAILABLE = (
    "Free generation is unavailable until its approved database migration is applied."
)
SUCCESS_STATUS = "completed"
PENDING_STATUS = "reserved"
FAILED_STATUS = "failed"


@dataclass(frozen=True)
class FreeGenerationReservation:
    reservation_key: bytes = field(repr=False)
    generation_id: int


def _require_schema(db: Session) -> None:
    try:
        inspector = inspect(db.connection())
        table = FreeGenerationAllowance.__table__
        if not inspector.has_table(table.name):
            raise HTTPException(status_code=503, detail=SCHEMA_UNAVAILABLE)
        actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
        if not set(table.columns.keys()) <= actual_columns:
            raise HTTPException(status_code=503, detail=SCHEMA_UNAVAILABLE)
        primary_key = tuple(
            inspector.get_pk_constraint(table.name).get("constrained_columns") or ()
        )
        if primary_key != ("user_id",):
            raise HTTPException(status_code=503, detail=SCHEMA_UNAVAILABLE)
        unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table.name)
        }
        unique_columns.update(
            tuple(index["column_names"])
            for index in inspector.get_indexes(table.name)
            if index.get("unique")
        )
        if ("generation_id",) not in unique_columns:
            raise HTTPException(status_code=503, detail=SCHEMA_UNAVAILABLE)
        actual_foreign_keys = {
            (
                tuple(foreign_key["constrained_columns"]),
                foreign_key["referred_table"],
                tuple(foreign_key["referred_columns"]),
            )
            for foreign_key in inspector.get_foreign_keys(table.name)
        }
        if not {
            (("user_id",), "User", ("id",)),
            (("generation_id",), "AIGeneration", ("id",)),
        } <= actual_foreign_keys:
            raise HTTPException(status_code=503, detail=SCHEMA_UNAVAILABLE)
        if db.bind is not None and db.bind.dialect.name == "mysql":
            engine_name = inspector.get_table_options(table.name).get("mysql_engine")
            if not isinstance(engine_name, str) or engine_name.casefold() != "innodb":
                raise HTTPException(status_code=503, detail=SCHEMA_UNAVAILABLE)
        check_names = {
            constraint.get("name")
            for constraint in inspector.get_check_constraints(table.name)
        }
        if "m005_ck_free_generation_state" not in check_names:
            raise HTTPException(status_code=503, detail=SCHEMA_UNAVAILABLE)
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail=SCHEMA_UNAVAILABLE) from None


def _require_normal_user(user: User) -> None:
    if user.role != "user":
        raise HTTPException(
            status_code=403,
            detail="This feature is only available to Normal Users.",
        )


def _locked_user(db: Session, user: User) -> User:
    current = lock_profile(db, user.id)
    if current is None:
        raise HTTPException(
            status_code=401,
            detail="Your session is invalid or has expired. Please sign in again.",
        )
    _require_normal_user(current)
    return current


def _allowance(
    db: Session, user_id: int, *, lock: bool = False
) -> FreeGenerationAllowance | None:
    query = select(FreeGenerationAllowance).where(
        FreeGenerationAllowance.user_id == user_id
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return db.scalar(query)


def _status_for(db: Session, user_id: int) -> str:
    allowance = _allowance(db, user_id)
    if allowance is None or allowance.state == "available":
        return "available"
    if allowance.state == "reserved":
        return "in_progress"
    if allowance.state == "consumed":
        return "used"
    raise HTTPException(status_code=503, detail="Free generation state is unavailable.")


def eligibility(db: Session, user: User) -> dict[str, object]:
    _require_normal_user(user)
    _require_schema(db)
    state = _status_for(db, user.id)
    return {
        "free_request_status": state,
        "free_request_available": state == "available",
    }


def reserve_free_request(
    db: Session,
    user: User,
    *,
    plan_id: int,
    quality: str,
    guidance_text: str | None = None,
) -> FreeGenerationReservation:
    """Reserve one preview before generation; caller must complete or release it."""
    _require_normal_user(user)
    _require_schema(db)
    try:
        current = _locked_user(db, user)
        plan = db.scalar(
            select(PhotographyPlan.id).where(
                PhotographyPlan.id == plan_id,
                PhotographyPlan.user_id == current.id,
            )
        )
        if plan is None:
            raise HTTPException(
                status_code=404, detail="This photography plan could not be found."
            )

        allowance = _allowance(db, current.id, lock=True)
        if allowance is None:
            allowance = FreeGenerationAllowance(
                user_id=current.id, state="available"
            )
            db.add(allowance)
            db.flush()
        if allowance.state != "available":
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="The free preview is already used or another request is in progress.",
            )

        token = secrets.token_bytes(32)
        now = _utc_now()
        generation = AIGeneration(
            user_id=current.id,
            plan_id=plan_id,
            quality=quality,
            status=PENDING_STATUS,
            guidance_text=guidance_text,
        )
        db.add(generation)
        db.flush()
        allowance.state = "reserved"
        allowance.reservation_key = token
        allowance.generation_id = generation.id
        allowance.reserved_at = now
        db.commit()
        return FreeGenerationReservation(token, generation.id)
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Unable to reserve the free preview. Please try again.",
        ) from None


def complete_free_request(
    db: Session,
    user: User,
    *,
    reservation: FreeGenerationReservation,
) -> None:
    """Consume the allowance only after its generation record is successful."""
    _require_normal_user(user)
    _require_schema(db)
    try:
        current = _locked_user(db, user)
        allowance = _allowance(db, current.id, lock=True)
        if (
            allowance is not None
            and allowance.state == "consumed"
            and allowance.generation_id == reservation.generation_id
        ):
            generation = _successful_generation(
                db, current.id, reservation.generation_id, lock=True
            )
            if generation is not None:
                db.rollback()
                return
        if not _matches_reservation(allowance, reservation):
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="The free preview reservation is no longer active.",
            )
        generation = _successful_generation(
            db, current.id, reservation.generation_id, lock=True
        )
        if generation is None:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="A successful generation record is required to use the free preview.",
            )
        allowance.state = "consumed"
        allowance.reservation_key = None
        allowance.consumed_at = _utc_now()
        db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Unable to complete the free preview. Please try again.",
        ) from None


def reconcile_interrupted_request(db: Session, *, user_id: int) -> str:
    """Finalize a persisted terminal request; leave nonterminal work reserved."""
    _require_schema(db)
    try:
        current = lock_profile(db, user_id)
        if current is None:
            raise HTTPException(status_code=404, detail="The account could not be found.")
        allowance = _allowance(db, current.id, lock=True)
        if allowance is None or allowance.state != "reserved":
            db.rollback()
            return _status_for(db, current.id)

        generation = db.scalar(
            select(AIGeneration)
            .where(
                AIGeneration.id == allowance.generation_id,
                AIGeneration.user_id == current.id,
            )
            .with_for_update()
        )
        if generation is None:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail="The reserved generation record is unavailable.",
            )

        if generation.status == SUCCESS_STATUS and generation.completed_at is not None:
            allowance.state = "consumed"
            allowance.reservation_key = None
            allowance.consumed_at = _utc_now()
        elif generation.status == FAILED_STATUS:
            allowance.state = "available"
            allowance.reservation_key = None
            allowance.generation_id = None
            allowance.reserved_at = None
        elif generation.status == PENDING_STATUS:
            db.rollback()
            return "in_progress"
        else:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail="The reserved generation has an unknown state and needs review.",
            )

        result = "used" if allowance.state == "consumed" else "available"
        db.commit()
        return result
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Unable to reconcile the interrupted free preview.",
        ) from None


def release_failed_request(
    db: Session,
    user: User,
    *,
    reservation: FreeGenerationReservation,
) -> None:
    """Release a failed attempt without consuming the account's free allowance."""
    _require_schema(db)
    try:
        current = db.get(User,user.id,populate_existing=True,with_for_update=True)
        if current is None: raise HTTPException(404,"Account not found.")
        allowance = _allowance(db, current.id, lock=True)
        if not _matches_reservation(allowance, reservation):
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="The free preview reservation is no longer active.",
            )
        generation = db.scalar(
            select(AIGeneration)
            .where(
                AIGeneration.id == reservation.generation_id,
                AIGeneration.user_id == current.id,
                AIGeneration.status == PENDING_STATUS,
            )
            .with_for_update()
        )
        if generation is None:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="The free preview generation is no longer active.",
            )
        generation.status = FAILED_STATUS
        generation.error_message = "Generation failed."
        allowance.state = "available"
        allowance.reservation_key = None
        allowance.generation_id = None
        allowance.reserved_at = None
        db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Unable to release the failed preview. Please try again.",
        ) from None


def _matches_reservation(
    allowance: FreeGenerationAllowance | None,
    reservation: FreeGenerationReservation,
) -> bool:
    return bool(
        allowance
        and allowance.state == "reserved"
        and allowance.generation_id == reservation.generation_id
        and allowance.reservation_key
        and secrets.compare_digest(
            allowance.reservation_key, reservation.reservation_key
        )
    )


def _successful_generation(
    db: Session, user_id: int, generation_id: int, *, lock: bool = False
) -> AIGeneration | None:
    query = select(AIGeneration).where(
        AIGeneration.id == generation_id,
        AIGeneration.user_id == user_id,
        AIGeneration.status == SUCCESS_STATUS,
        AIGeneration.completed_at.is_not(None),
    )
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
