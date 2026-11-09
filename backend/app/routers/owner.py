"""Authenticated Studio Owner onboarding; no public studio data or plan activation."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.models.user import User
from app.schemas.ai import GenerationResponse
from app.schemas.owner import OwnerOnboarding, StudioUpdate
from app.services import onboarding_service
from app.services import ai_service, plan_service
from app.schemas.photography_plan import PhotographyPlanRead


def owner_request(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    history_page = (
        request.url.path == "/owner/account-history/generations"
        and len(request.query_params.multi_items()) == 1
        and request.query_params.get("before") is not None
    )
    if request.query_params and not history_page:
        raise HTTPException(422, "Query parameters are not supported.")


router = APIRouter(prefix="/owner", tags=["Owner onboarding"], dependencies=[Depends(owner_request)])
owner_identity = require_roles("owner")


@router.get("/onboarding", response_model=OwnerOnboarding)
def get_onboarding(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return onboarding_service.get_onboarding(db, user)


@router.get("/account-history/photography-plans", response_model=list[PhotographyPlanRead])
def account_history_plans(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return plan_service.list_plans(db, user)


@router.get("/account-history/generations", response_model=list[GenerationResponse])
def account_history_generations(before: int | None = Query(None, gt=0),
                                 user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return ai_service.list_generations(db, user, before=before)


@router.get("/account-history/images/{asset_id}")
def account_history_image(asset_id: int, user: User = Depends(owner_identity),
                          db: Session = Depends(get_db)):
    return Response(ai_service.get_image(db, user, asset_id), media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'inline; filename="frameora.png"',
    })


@router.put("/studio", response_model=OwnerOnboarding)
def put_studio(data: StudioUpdate, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return onboarding_service.update_studio(db, user, data)


@router.get('/studio/photo-status')
def studio_photo_status(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    from app.services import studio_photo_service
    return studio_photo_service.status(db, user)


@router.post('/studio/photo')
async def upload_studio_photo(request: Request, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    from starlette.concurrency import run_in_threadpool
    from app.services import studio_photo_service, profile_image_storage
    if request.headers.get('content-type', '').split(';', 1)[0].lower() not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(415, 'Send raw JPEG, PNG or WebP image bytes.')
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > profile_image_storage.MAX_UPLOAD:
            raise HTTPException(413, 'Studio photos must not exceed 5 MiB.')
        data.extend(chunk)
    return await run_in_threadpool(studio_photo_service.change, db, user, bytes(data))


@router.delete('/studio/photo')
def remove_studio_photo(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    from app.services import studio_photo_service
    return studio_photo_service.change(db, user, None)


@router.get('/studio/photo')
def studio_photo(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    from app.services import studio_photo_service
    return Response(studio_photo_service.read(db, user), media_type='image/png',
                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Pragma': 'no-cache'})
