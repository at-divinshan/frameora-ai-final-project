from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database.connection import get_db
from app.models.user import User
from app.routers.owner import owner_request
from app.schemas.sharing import ShareLinkCreate, ShareLinkCreated, ShareLinkRead, SharedGeneration
from app.services import share_service

router = APIRouter(tags=["Sharing"])
owner_identity = require_roles("owner")


@router.post(
    "/owner/projects/{project_id}/share-links",
    response_model=ShareLinkCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(owner_request)],
)
def create_project_share_link(
    project_id: int,
    data: ShareLinkCreate,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return share_service.create_link(db, user, project_id, data.generation_id, data.expires_at)


@router.get(
    "/owner/projects/{project_id}/share-links",
    response_model=list[ShareLinkRead],
    dependencies=[Depends(owner_request)],
)
def list_project_share_links(
    project_id: int,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    return share_service.list_links(db, user, project_id)


@router.delete(
    "/owner/projects/{project_id}/share-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(owner_request)],
)
def deactivate_project_share_link(
    project_id: int,
    link_id: int,
    user: User = Depends(owner_identity),
    db: Session = Depends(get_db),
):
    share_service.deactivate_link(db, user, project_id, link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sharing/{token}", response_model=SharedGeneration)
def shared_generation(
    token: str,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return share_service.view_shared_generation(db, user, token)


@router.get("/sharing/{token}/images/{asset_id}")
def shared_image(
    token: str,
    asset_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return Response(
        share_service.read_shared_image(db, user, token, asset_id),
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="frameora.png"',
        },
    )