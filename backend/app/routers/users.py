"""JWT-authenticated self-profile access for all existing account roles."""

from fastapi import APIRouter, Depends, Response, Path, Request, HTTPException
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.user import ProfileUpdate, SelfProfile
from app.schemas.user import PrivacySettings, PrivacyUpdate, PublicProfile
from app.services import user_service
from app.services import profile_image_service, profile_image_storage


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


router = APIRouter(prefix="/users", tags=["Profile"], dependencies=[Depends(no_store)])


@router.post("/me/picture")
async def upload_picture(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send raw JPEG/PNG bytes, not multipart; bound memory before image decoding."""
    if request.headers.get("content-type", "").split(";", 1)[0].lower() not in ("image/jpeg", "image/png"):
        raise HTTPException(415, "Send JPEG or PNG image bytes.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > profile_image_storage.MAX_UPLOAD:
            raise HTTPException(413, "Profile pictures must not exceed 5 MiB.")
        data.extend(chunk)
    return await run_in_threadpool(profile_image_service.change_picture, db, user, bytes(data))


@router.delete("/me/picture")
def remove_picture(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_image_service.change_picture(db, user, None)


@router.get("/me/picture")
def own_picture(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response(profile_image_service.get_picture(db, user.id, public=False), media_type="image/png")


@router.get("/{user_id}/picture")
def visible_picture(user_id: int = Path(ge=1, le=2147483647), db: Session = Depends(get_db)):
    return Response(profile_image_service.get_picture(db, user_id, public=True), media_type="image/png")


@router.get("/me", response_model=SelfProfile)
def get_profile(user: User = Depends(get_current_user)):
    return user_service.self_profile(user)


@router.patch("/me", response_model=SelfProfile)
def patch_profile(data: ProfileUpdate, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return user_service.update_profile(db, user, data)


@router.get("/me/privacy", response_model=PrivacySettings)
def get_privacy(user: User = Depends(get_current_user)):
    return user_service.privacy_settings(user)


@router.patch("/me/privacy", response_model=PrivacySettings)
def patch_privacy(data: PrivacyUpdate, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return user_service.update_privacy(db, user, data)


@router.get("/{user_id}/public-profile", response_model=PublicProfile)
def get_public_profile(user_id: int = Path(ge=1, le=2147483647), db: Session = Depends(get_db)):
    return user_service.public_profile(db, user_id)
