"""Authenticated AI generation, private media, and free allowance eligibility."""

from fastapi import APIRouter, Depends, Response, File, Form, HTTPException, Query, UploadFile, Request
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.models.user import User
from app.schemas.ai import FreeGenerationEligibility, GenerationResponse
from app.services import free_generation_service, ai_service, ai_image_storage

router = APIRouter(prefix="/ai", tags=["AI generation"])
normal_user = require_roles("user")


@router.get(
    "/free-generation/eligibility",
    response_model=FreeGenerationEligibility,
)
def free_generation_eligibility(
    response: Response,
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return free_generation_service.eligibility(db, user)

async def reference_fields(request: Request):
    form = await request.form()
    for name in ('reference', 'reference_photo', 'background_reference'):
        if len(form.getlist(name)) > 1:
            raise HTTPException(422, 'Upload each reference only once.')

@router.post("/generations", response_model=GenerationResponse, status_code=201, dependencies=[Depends(reference_fields)])
def generate_images(
    response: Response,
    plan_id: int = Form(..., gt=0),
    description: str = Form("", max_length=2000),
    reference: UploadFile | None = File(None),
    reference_photo: UploadFile | None = File(None),
    background_reference: UploadFile | None = File(None),
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    from app.routers.owner_ai import _normalize_reference_fields, _normalize_reference
    normalized = _normalize_reference_fields(reference, reference_photo)
    background = _normalize_reference(background_reference)
    return ai_service.generate(db, user, plan_id=plan_id, description=description.strip(),
                               reference=normalized, background_reference=background)



@router.get("/generations", response_model=list[GenerationResponse])
def my_generations(
    response: Response,
    before: int | None = Query(None, gt=0),
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return ai_service.list_generations(db, user, before=before)


@router.get("/images/{asset_id}")
def my_image(asset_id: int, user: User = Depends(normal_user), db: Session = Depends(get_db)):
    return Response(ai_service.get_image(db, user, asset_id), media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'inline; filename="frameora.png"',
    })


@router.get('/gallery/folders')
def gallery_folders(response: Response, user: User = Depends(require_roles('user', 'owner')),
                    db: Session = Depends(get_db)):
    from app.services.gallery_service import folders
    response.headers['Cache-Control'] = 'private, no-store'
    return folders(db, user)


@router.get('/gallery/folders/{key}')
def gallery_contents(key: str, response: Response, before: int | None = Query(None, gt=0),
                     user: User = Depends(require_roles('user', 'owner')), db: Session = Depends(get_db)):
    from app.services.gallery_service import contents
    response.headers['Cache-Control'] = 'private, no-store'
    return contents(db, user, key, before)
