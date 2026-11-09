"""Authenticated Normal User photography plan operations."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import plan_repository, project_repository
from app.schemas.photography_plan import (
    PhotographyPlanCreate,
    PhotographyPlanPatch,
    PhotographyPlanRead,
)
from app.services import project_service


PLAN_NOT_FOUND = "Photography plan not found."


def _validate_owner_plan_project(db: Session, user: User, plan) -> bool:
    if plan.project_id is None:
        return True
    return project_repository.find_active(db, user.id, plan.project_id) is not None


def _merge_preferences(existing, incoming):
    if incoming is None or not isinstance(incoming, dict):
        return incoming

    merged = dict(existing) if isinstance(existing, dict) else {}
    for key, value in incoming.items():
        if key == "equipment":
            if value is None:
                merged.pop(key, None)
                continue
            if isinstance(value, dict):
                equipment = dict(merged.get(key)) if isinstance(merged.get(key), dict) else {}
                equipment.update(value)
                equipment = {name: item for name, item in equipment.items() if item is not None}
                if equipment:
                    merged[key] = equipment
                else:
                    merged.pop(key, None)
                continue
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged or None


def list_plans(db: Session, user: User) -> list[PhotographyPlanRead]:
    return [PhotographyPlanRead.model_validate(plan) for plan in plan_repository.list_for_user(db, user.id)]


def list_owner_plans(db: Session, user: User) -> list[PhotographyPlanRead]:
    return [
        PhotographyPlanRead.model_validate(plan)
        for plan in plan_repository.list_for_user(db, user.id)
        if _validate_owner_plan_project(db, user, plan)
    ]


def create_plan(db: Session, user: User, data: PhotographyPlanCreate) -> PhotographyPlanRead:
    try:
        values = data.model_dump()
        values["preferences"] = _merge_preferences(None, values["preferences"])
        plan = plan_repository.create_for_user(
            db,
            user.id,
            values,
        )
        db.refresh(plan)
        result = PhotographyPlanRead.model_validate(plan)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def create_project_plan(
    db: Session, user: User, project_id: int, data: PhotographyPlanCreate
) -> PhotographyPlanRead:
    try:
        project_service.require_project_access(db, user, project_id, editable=True)
        values = data.model_dump()
        values["preferences"] = _merge_preferences(None, values["preferences"])
        plan = plan_repository.create_for_user(db, user.id, values, project_id=project_id)
        db.refresh(plan)
        result = PhotographyPlanRead.model_validate(plan)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def list_project_plans(
    db: Session, user: User, project_id: int
) -> list[PhotographyPlanRead]:
    try:
        project_service.require_project_access(db, user, project_id, editable=False)
        result = [
            PhotographyPlanRead.model_validate(plan)
            for plan in plan_repository.list_for_project(db, user.id, project_id)
        ]
        db.rollback()
        return result
    except Exception:
        db.rollback()
        raise


def link_plan_to_project(
    db: Session, user: User, project_id: int, plan_id: int
) -> PhotographyPlanRead:
    try:
        project_service.require_project_access(db, user, project_id, editable=True)
        plan = plan_repository.find_for_user(db, user.id, plan_id)
        if plan is None or not _validate_owner_plan_project(db, user, plan):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PLAN_NOT_FOUND)
        if plan.project_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Photography plan is already linked to a project.",
            )
        plan = plan_repository.link_to_project(db, plan, project_id)
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


def get_owner_plan(db: Session, user: User, plan_id: int) -> PhotographyPlanRead:
    plan = plan_repository.find_for_user(db, user.id, plan_id)
    if plan is None or not _validate_owner_plan_project(db, user, plan):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PLAN_NOT_FOUND)
    return PhotographyPlanRead.model_validate(plan)


def update_plan(
    db: Session,
    user: User,
    plan_id: int,
    data: PhotographyPlanPatch,
) -> PhotographyPlanRead:
    try:
        existing_plan = plan_repository.find_for_user(db, user.id, plan_id)
        if existing_plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PLAN_NOT_FOUND)
        values = data.model_dump(exclude_unset=True)
        if "preferences" in values:
            values["preferences"] = _merge_preferences(existing_plan.preferences, values["preferences"])
        plan = plan_repository.update_for_user(
            db,
            user.id,
            plan_id,
            values,
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


def update_owner_plan(
    db: Session, user: User, plan_id: int, data: PhotographyPlanPatch
) -> PhotographyPlanRead:
    try:
        plan = plan_repository.find_for_user(db, user.id, plan_id)
        if plan is None or not _validate_owner_plan_project(db, user, plan):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PLAN_NOT_FOUND)
        if plan.project_id is not None:
            project_service.require_project_access(db, user, plan.project_id, editable=True)
    except Exception:
        db.rollback()
        raise
    return update_plan(db, user, plan_id, data)


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