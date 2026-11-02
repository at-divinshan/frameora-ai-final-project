"""Authenticated Normal User photography plan operations."""

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import plan_repository
from app.schemas.photography_plan import PhotographyPlanCreate, PhotographyPlanRead


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