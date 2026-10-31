"""Owner-only subscriptions. No payment or arbitrary plan activation endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.user import User
from app.routers.owner import owner_identity, owner_request
from app.schemas.subscription import ActivationRequest, Entitlements
from app.services import subscription_service as service

router = APIRouter(prefix='/owner', tags=['Owner subscriptions'], dependencies=[Depends(owner_request)])

@router.get('/plans')
def plans(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return service.catalogue(db, user)

@router.get('/subscription', response_model=Entitlements)
def subscription(user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return service.snapshot(db, user)

@router.post('/subscription/basic', response_model=Entitlements)
def basic(data: ActivationRequest, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return service.snapshot(db, user, 'basic', data.idempotency_key)

@router.post('/subscription/trial', response_model=Entitlements)
def trial(data: ActivationRequest, user: User = Depends(owner_identity), db: Session = Depends(get_db)):
    return service.snapshot(db, user, 'trial', data.idempotency_key)
