from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user, require_roles
from app.database.connection import get_db
from app.routers.owner import owner_request
from app.schemas.feedback import CommentCreate, FeedbackUpdate
from app.services import feedback_service as service

router=APIRouter(tags=["Image feedback"])

def no_store(response: Response):
    response.headers["Cache-Control"]="private, no-store"
    response.headers["X-Content-Type-Options"]="nosniff"

@router.get('/sharing/{token}/images/{asset_id}/comments', dependencies=[Depends(no_store)])
def comments(token: str,asset_id: int,user=Depends(get_current_user),db: Session=Depends(get_db)):
    return service.customer_comments(db,user,token,asset_id)

@router.post('/sharing/{token}/images/{asset_id}/comments', dependencies=[Depends(no_store)],status_code=201)
def comment(token: str,asset_id: int,data: CommentCreate,user=Depends(get_current_user),db: Session=Depends(get_db)):
    return service.customer_comments(db,user,token,asset_id,data)

@router.get('/owner/projects/{project_id}/feedback', dependencies=[Depends(owner_request),Depends(no_store)])
def feedback(project_id: int,user=Depends(require_roles('owner')),db: Session=Depends(get_db)):
    return service.owner_feedback(db,user,project_id)

@router.patch('/owner/projects/{project_id}/feedback/{feedback_id}', dependencies=[Depends(owner_request),Depends(no_store)])
def update(project_id: int,feedback_id: int,data: FeedbackUpdate,user=Depends(require_roles('owner')),db: Session=Depends(get_db)):
    return service.owner_feedback(db,user,project_id,feedback_id,data)
