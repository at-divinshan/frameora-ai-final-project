"""Queries for the existing PhotographyPlan table."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_generation import AIGeneration
from app.models.photography_plan import PhotographyPlan


def list_for_user(db: Session, user_id: int) -> list[PhotographyPlan]:
    return list(
        db.scalars(
            select(PhotographyPlan)
            .where(PhotographyPlan.user_id == user_id)
            .order_by(PhotographyPlan.created_at.desc(), PhotographyPlan.id.desc())
        )
    )


def create_for_user(db: Session, user_id: int, values: dict) -> PhotographyPlan:
    plan = PhotographyPlan(user_id=user_id, project_id=None, **values)
    db.add(plan)
    db.flush()
    return plan


def find_for_user(db: Session, user_id: int, plan_id: int) -> PhotographyPlan | None:
    return db.scalar(
        select(PhotographyPlan).where(
            PhotographyPlan.id == plan_id,
            PhotographyPlan.user_id == user_id,
        )
    )


def update_for_user(
    db: Session,
    user_id: int,
    plan_id: int,
    values: dict,
) -> PhotographyPlan | None:
    plan = find_for_user(db, user_id, plan_id)
    if plan is None:
        return None
    for field, value in values.items():
        setattr(plan, field, value)
    db.flush()
    return plan


def delete_for_user(db: Session, user_id: int, plan_id: int) -> tuple[bool, bool]:
    plan = find_for_user(db, user_id, plan_id)
    if plan is None:
        return False, False

    has_generation_history = db.scalar(
        select(AIGeneration.id)
        .join(PhotographyPlan, AIGeneration.plan_id == PhotographyPlan.id)
        .where(
            PhotographyPlan.id == plan_id,
            PhotographyPlan.user_id == user_id,
        )
        .limit(1)
    )
    if has_generation_history is not None:
        return True, True

    db.delete(plan)
    db.flush()
    return True, False