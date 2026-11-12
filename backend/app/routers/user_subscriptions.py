"""Read-only Normal User catalogue. Paid activation requires future verified payment."""
from fastapi import APIRouter, Depends, Response
from app.core.dependencies import require_roles
from app.services.user_subscription_catalogue import catalogue

router = APIRouter(prefix='/user/subscription', tags=['Normal User subscriptions'])

@router.get('/plans')
def plans(response: Response, user=Depends(require_roles('user'))):
    response.headers['Cache-Control'] = 'private, no-store'
    return catalogue()
