from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.orm import Session
from app.core.dependencies import require_roles
from app.database.connection import get_db
from app.services import notification_service as service

router=APIRouter(prefix='/notifications',tags=['Notifications'])
class ReadState(BaseModel):
    model_config=ConfigDict(extra='forbid')
    is_read: StrictBool

def private(response:Response):
    response.headers['Cache-Control']='private, no-store'

@router.get('',dependencies=[Depends(private)])
def inbox(before:int|None=Query(None,gt=0),limit:int=Query(20,ge=1,le=50),user=Depends(require_roles('owner','user')),db:Session=Depends(get_db)):
    return service.inbox(db,user,before,limit)

@router.patch('/{notification_id}',dependencies=[Depends(private)])
def mark(notification_id:int,data:ReadState,user=Depends(require_roles('owner','user')),db:Session=Depends(get_db)):
    return service.mark(db,user,notification_id,data.is_read)
