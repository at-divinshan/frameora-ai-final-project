from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.services import live_pose_service as service
from app.services.live_pose_provider import get_scene_provider, validate_snapshot

router = APIRouter(prefix="/live-pose", tags=["Live Pose Guide"])
identity = require_roles("user", "owner")

class SceneRequest(BaseModel):
    session_id: UUID
    snapshot: str = Field(min_length=1, max_length=1400000)

@router.get("/entitlements")
def entitlements(user=Depends(identity), db: Session=Depends(get_db), provider=Depends(get_scene_provider)):
    return service.entitlements(db, user, provider)

@router.post("/analyze")
def analyze(data: SceneRequest, user=Depends(identity), db: Session=Depends(get_db), provider=Depends(get_scene_provider)):
    return service.analyze(db, user, str(data.session_id), validate_snapshot(data.snapshot), provider)
