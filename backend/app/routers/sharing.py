from fastapi import APIRouter, Depends, Response, status, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database.connection import get_db
from app.models.user import User
from app.routers.owner import owner_request
from app.schemas.sharing import ShareLinkCreate, ShareLinkCreated, ShareLinkRead, SharedGeneration, ShareLinkStatusUpdate
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


@router.put('/owner/projects/{project_id}/share-links/{link_id}/phases/{phase_id}', dependencies=[Depends(owner_request)])
def publish_project_phase(project_id: int, link_id: int, phase_id: int,
                          user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    from app.services.project_phase_service import publish
    return publish(db, user, project_id, link_id, phase_id)


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
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="frameora-preview.jpg"',
        },
    )

@router.get('/owner/share-links', dependencies=[Depends(owner_request)])
def owner_share_links(response: Response, project_id: int | None = Query(None, gt=0), before: int | None = Query(None, gt=0),
                      user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return share_service.management_links(db, user, project_id=project_id, before=before)



@router.patch('/owner/projects/{project_id}/share-links/{link_id}', response_model=ShareLinkRead,
              dependencies=[Depends(owner_request)])
def update_share_link_status(project_id: int, link_id: int, data: ShareLinkStatusUpdate,
                             user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    if data.is_active:
        return share_service.activate_link(db, user, project_id, link_id)
    return share_service.deactivate_link(db, user, project_id, link_id)
