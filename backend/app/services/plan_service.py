"""Authenticated Normal User photography plan operations."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import plan_repository
from app.schemas.photography_plan import (
    PhotographyPlanCreate,
    PhotographyPlanPatch,
    PhotographyPlanRead,
)


PLAN_NOT_FOUND = "Photography plan not found."


def list_plans(db: Session, user: User) -> list[PhotographyPlanRead]:
    return [PhotographyPlanRead.model_validate(plan) for plan in plan_repository.list_for_user(db, user.id)]


def create_plan(db: Session, user: User, data: PhotographyPlanCreate) -> PhotographyPlanRead:
    try:
        plan = plan_repository.create_for_user(
            db,
            user.id,
            data.model_dump(),
        )
        db.refresh(plan)
        result = PhotographyPlanRead.model_validate(plan)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def get_plan(db: Session, user: User, plan_id: int) -> PhotographyPlanRead:
    plan = plan_repository.find_for_user(db, user.id, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PLAN_NOT_FOUND)
    return PhotographyPlanRead.model_validate(plan)


def update_plan(
    db: Session,
    user: User,
    plan_id: int,
    data: PhotographyPlanPatch,
) -> PhotographyPlanRead:
    try:
        plan = plan_repository.update_for_user(
            db,
            user.id,
            plan_id,
            data.model_dump(exclude_unset=True),
        )
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PLAN_NOT_FOUND)
        db.refresh(plan)
        result = PhotographyPlanRead.model_validate(plan)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def delete_plan(db: Session, user: User, plan_id: int) -> None:
    try:
        found, has_generation_history = plan_repository.delete_for_user(db, user.id, plan_id)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PLAN_NOT_FOUND)
        if has_generation_history:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This plan cannot be deleted while generation history is linked to it.",
            )
        db.commit()
    except Exception:
        db.rollback()
        raise