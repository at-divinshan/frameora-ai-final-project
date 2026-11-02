"""Queries for the existing PhotographyPlan table."""

from sqlalchemy import select
from sqlalchemy.orm import Session

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