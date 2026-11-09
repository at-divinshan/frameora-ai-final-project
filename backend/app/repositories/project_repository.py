"""Owner-scoped queries for the existing CustomerProject table."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer_project import CustomerProject


def list_active(db: Session, owner_id: int) -> list[CustomerProject]:
    return list(
        db.scalars(
            select(CustomerProject)
            .where(
                CustomerProject.studio_owner_id == owner_id,
                CustomerProject.deleted_at.is_(None),
            )
            .order_by(CustomerProject.created_at.asc(), CustomerProject.id.asc())
        )
    )


def find_active(db: Session, owner_id: int, project_id: int) -> CustomerProject | None:
    return db.scalar(
        select(CustomerProject).where(
            CustomerProject.id == project_id,
            CustomerProject.studio_owner_id == owner_id,
            CustomerProject.deleted_at.is_(None),
        )
    )


def count_active(db: Session, owner_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(CustomerProject)
        .where(
            CustomerProject.studio_owner_id == owner_id,
            CustomerProject.deleted_at.is_(None),
        )
    ) or 0


def create(db: Session, owner_id: int, values: dict) -> CustomerProject:
    project = CustomerProject(studio_owner_id=owner_id, **values)
    db.add(project)
    db.flush()
    db.refresh(project)
    return project