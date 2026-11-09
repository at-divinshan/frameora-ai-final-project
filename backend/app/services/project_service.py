"""Owner project CRUD and plan-based editability enforcement."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.customer_project import CustomerProject
from app.models.user import User
from app.repositories import project_repository
from app.repositories.user_repository import lock_profile
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import owner_entitlement_service, subscription_service
from app.services.onboarding_service import require_owner


def _locked_owner(db: Session, user: User) -> User:
    owner = lock_profile(db, user.id)
    require_owner(owner)
    return owner


def _project_limit(db: Session, owner: User, *, persist_expiry: bool) -> int:
    _, entitlement = owner_entitlement_service.resolve_locked(
        db,
        owner,
        now=subscription_service.clock(),
        persist=persist_expiry,
        grant=False,
    )
    limit = entitlement["max_projects"]
    if not entitlement["plan"] or limit < 1:
        raise HTTPException(409, "Select an owner subscription before managing projects.")
    return limit


def _editable_ids(projects: list[CustomerProject], limit: int) -> set[int]:
    return {project.id for project in projects[:limit]}


def require_project_access(
    db: Session, user: User, project_id: int, *, editable: bool
) -> CustomerProject:
    owner = _locked_owner(db, user)
    project = project_repository.find_active(db, owner.id, project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    limit = _project_limit(db, owner, persist_expiry=editable)
    if editable:
        ordered = project_repository.list_active(db, owner.id)
        if project.id not in _editable_ids(ordered, limit):
            raise HTTPException(409, "This project is read-only under your current plan.")
    return project


def _response(project: CustomerProject, editable: bool) -> ProjectResponse:
    return ProjectResponse.model_validate(
        {
            "id": project.id,
            "customer_name": project.customer_name,
            "project_title": project.project_title,
            "customer_contact": project.customer_contact,
            "event_type": project.event_type,
            "shoot_location": project.shoot_location,
            "shooting_date": project.shooting_date,
            "requirements": project.requirements,
            "created_at": project.created_at,
            "is_editable": editable,
        }
    )


def list_projects(db: Session, user: User) -> list[ProjectResponse]:
    try:
        owner = _locked_owner(db, user)
        limit = _project_limit(db, owner, persist_expiry=False)
        projects = project_repository.list_active(db, owner.id)
        editable = _editable_ids(projects, limit)
        result = [_response(project, project.id in editable) for project in projects]
        db.rollback()
        return result
    except Exception:
        db.rollback()
        raise


def get_project(db: Session, user: User, project_id: int) -> ProjectResponse:
    try:
        owner = _locked_owner(db, user)
        limit = _project_limit(db, owner, persist_expiry=False)
        project = project_repository.find_active(db, owner.id, project_id)
        if project is None:
            raise HTTPException(404, "Project not found.")
        ordered = project_repository.list_active(db, owner.id)
        result = _response(project, project.id in _editable_ids(ordered, limit))
        db.rollback()
        return result
    except Exception:
        db.rollback()
        raise


def create_project(db: Session, user: User, data: ProjectCreate) -> ProjectResponse:
    try:
        owner = _locked_owner(db, user)
        limit = _project_limit(db, owner, persist_expiry=True)
        if project_repository.count_active(db, owner.id) >= limit:
            raise HTTPException(409, "Your subscription project limit has been reached.")
        project = project_repository.create(db, owner.id, data.model_dump())
        result = _response(project, True)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def update_project(
    db: Session, user: User, project_id: int, data: ProjectUpdate
) -> ProjectResponse:
    try:
        owner = _locked_owner(db, user)
        limit = _project_limit(db, owner, persist_expiry=True)
        project = project_repository.find_active(db, owner.id, project_id)
        if project is None:
            raise HTTPException(404, "Project not found.")
        ordered = project_repository.list_active(db, owner.id)
        if project.id not in _editable_ids(ordered, limit):
            raise HTTPException(409, "This project is read-only under your current plan.")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        db.flush()
        result = _response(project, True)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise