"""Authenticated AI generation, private media, and free allowance eligibility."""

from fastapi import APIRouter, Depends, Response, File, Form, HTTPException, Query, UploadFile
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

@router.post("/generations", response_model=GenerationResponse, status_code=201)
def generate_images(
    response: Response,
    plan_id: int = Form(..., gt=0),
    description: str = Form("", max_length=2000),
    reference: UploadFile | None = File(None),
    user: User = Depends(normal_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    normalized = None
    if reference is not None:
        try:
            if reference.content_type not in ("image/jpeg", "image/png", "image/webp"):
                raise HTTPException(422, "Upload a JPEG, PNG or WebP reference image.")
            data = reference.file.read(ai_image_storage.MAX_UPLOAD + 1)
            if len(data) > ai_image_storage.MAX_UPLOAD:
                raise HTTPException(413, "Reference images must not exceed 5 MiB.")
            normalized = ai_image_storage.normalize_image(data)
        finally:
            reference.file.close()
    return ai_service.generate(db, user, plan_id=plan_id, description=description.strip(), reference=normalized)


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
