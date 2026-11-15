"""Fail-closed payment preparation. No checkout, activation or ledger writes."""
from fastapi import APIRouter, Depends, Response, Request, HTTPException
from app.database.connection import get_db
from app.services.stripe_test_provider import MAX_WEBHOOK_BYTES
from app.core.dependencies import require_roles
from app.schemas.payment import OwnerCheckoutRequest, UserCheckoutRequest
from app.services import payment_service

router = APIRouter(tags=['Payment preparation'])

@router.get('/owner/payments/readiness')
def readiness(response: Response, user=Depends(require_roles('owner'))):
    response.headers['Cache-Control'] = 'no-store'
    return payment_service.readiness(user)

@router.post('/owner/payments/checkout')
def checkout(data: OwnerCheckoutRequest, user=Depends(require_roles('owner')), db=Depends(get_db)):
    return payment_service.checkout(user, data, db)

@router.get('/user/payments/readiness')
def user_readiness(response: Response, user=Depends(require_roles('user'))):
    response.headers['Cache-Control'] = 'no-store'
    return payment_service.readiness(user)

@router.post('/user/payments/checkout')
def user_checkout(data: UserCheckoutRequest, user=Depends(require_roles('user')), db=Depends(get_db)):
    return payment_service.checkout(user, data, db)

@router.get('/user/payments/subscription')
def user_subscription(response: Response, user=Depends(require_roles('user')), db=Depends(get_db)):
    from app.services.user_payment_subscription import status
    response.headers['Cache-Control'] = 'no-store'
    return status(db, user)

@router.post('/payments/stripe/webhook')
async def stripe_webhook(request: Request, db=Depends(get_db)):
    from app.core.stripe_test import require_release
    require_release()
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_WEBHOOK_BYTES:
            raise HTTPException(413, 'Webhook is too large.')
    return payment_service.receive_webhook(bytes(raw), request.headers.get('stripe-signature', ''), db)
