"""Single-admin policy is enforced by the existing JWT/database dependency."""
from typing import Annotated
from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session
from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.schemas.admin import AdminSummary, OwnerFilters, OwnerPage, OwnerDetail
from app.services import admin_service, studio_photo_service


def no_store(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'

router = APIRouter(prefix='/admin', tags=['Admin read-only'], dependencies=[Depends(require_roles('admin')), Depends(no_store)])

@router.get('/summary', response_model=AdminSummary)
def summary(db: Session = Depends(get_db)):
    return admin_service.summary(db)

@router.get('/owners', response_model=OwnerPage)
def owners(filters: Annotated[OwnerFilters, Query()], db: Session = Depends(get_db)):
    return admin_service.owners(db, filters)

@router.get('/owners/{owner_id}', response_model=OwnerDetail)
def owner_detail(owner_id: int = Path(ge=1, le=2147483647), db: Session = Depends(get_db)):
    return admin_service.detail(db, owner_id)

@router.get('/owners/{owner_id}/photo')
def owner_photo(owner_id: int = Path(ge=1, le=2147483647), db: Session = Depends(get_db)):
    return Response(studio_photo_service.read(db, admin_service.owner(db, owner_id)), media_type='image/png',
        headers={'Cache-Control':'no-store','Pragma':'no-cache','X-Content-Type-Options':'nosniff'})
