from typing import Annotated
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.routers.admin import no_store
from app.schemas.admin_users import UserFilters, StatusChange
from app.services import admin_users_service as service
router=APIRouter(prefix='/admin/users',tags=['Admin user management'],dependencies=[Depends(no_store)])
@router.get('')
def users(filters:Annotated[UserFilters,Query()],admin=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    return service.listing(db,admin,filters)
@router.get('/{user_id}')
def detail(user_id:int=Path(gt=0),payment_page:int=Query(default=1,ge=1,le=10000),admin=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    return service.detail(db,admin,user_id,payment_page)
@router.patch('/{user_id}/status')
def change(data:StatusChange,user_id:int=Path(gt=0),admin=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    return service.change(db,admin,user_id,data)
