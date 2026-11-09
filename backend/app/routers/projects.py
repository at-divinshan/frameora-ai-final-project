"""Studio Owner customer-project endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.models.user import User
from app.routers.owner import owner_request
from app.schemas.photography_plan import PhotographyPlanCreate, PhotographyPlanRead
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import plan_service, project_service


router = APIRouter(
    prefix="/owner/projects",
    tags=["Owner projects"],
    dependencies=[Depends(owner_request)],
)
owner_identity = require_roles("owner")


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return project_service.create_project(db, user, data)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return project_service.list_projects(db, user)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return project_service.get_project(db, user, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return project_service.update_project(db, user, project_id, data)


@router.post(
    "/{project_id}/photography-plans",
    response_model=PhotographyPlanRead,
    status_code=201,
)
def create_project_plan(
    project_id: int,
    data: PhotographyPlanCreate,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return plan_service.create_project_plan(db, user, project_id, data)


@router.get(
    "/{project_id}/photography-plans",
    response_model=list[PhotographyPlanRead],
)
def list_project_plans(
    project_id: int,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return plan_service.list_project_plans(db, user, project_id)


@router.post(
    "/{project_id}/photography-plans/{plan_id}",
    response_model=PhotographyPlanRead,
)
def link_project_plan(
    project_id: int,
    plan_id: int,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return plan_service.link_plan_to_project(db, user, project_id, plan_id)