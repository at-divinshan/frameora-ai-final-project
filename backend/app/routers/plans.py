"""Normal User photography plan endpoints."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.models.user import User
from app.schemas.photography_plan import PhotographyPlanCreate, PhotographyPlanRead
from app.services import plan_service


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


router = APIRouter(
    prefix="/plans",
    tags=["Photography plans"],
    dependencies=[Depends(no_store)],
)
normal_user = require_roles("user")


@router.post("", response_model=PhotographyPlanRead, status_code=status.HTTP_201_CREATED)
def create_plan(
    data: PhotographyPlanCreate,
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    return plan_service.create_plan(db, user, data)


@router.get("", response_model=list[PhotographyPlanRead])
def list_plans(
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    return plan_service.list_plans(db, user)