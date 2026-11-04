"""Normal User photography plan endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.models.user import User
from app.schemas.photography_suggestions import PhotographySuggestions
from app.schemas.photography_plan import (
    PhotographyPlanCreate,
    PhotographyPlanPatch,
    PhotographyPlanRead,
)
from app.services import plan_service
from app.services.photography_suggestions import get_plan_suggestions
from app.services.suggestions_provider import (
    SuggestionsProvider,
    SuggestionsProviderError,
    SuggestionsProviderUnavailable,
    get_suggestions_provider,
)


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


@router.get("/{plan_id}", response_model=PhotographyPlanRead)
def get_plan(
    plan_id: int,
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    return plan_service.get_plan(db, user, plan_id)


@router.post("/{plan_id}/suggestions", response_model=PhotographySuggestions)
async def create_plan_suggestions(
    plan_id: int,
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
    provider: SuggestionsProvider = Depends(get_suggestions_provider),
):
    try:
        return await get_plan_suggestions(db, user, plan_id, provider)
    except SuggestionsProviderUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photography suggestions are not available yet. Please try again later.",
        ) from None
    except SuggestionsProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Photography suggestions could not be generated. Please try again later.",
        ) from None


@router.patch("/{plan_id}", response_model=PhotographyPlanRead)
def update_plan(
    plan_id: int,
    data: PhotographyPlanPatch,
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    return plan_service.update_plan(db, user, plan_id, data)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: int,
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    plan_service.delete_plan(db, user, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)