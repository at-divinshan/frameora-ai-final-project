"""Public email verification; links never authenticate users."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.database.connection import get_db
from app.services import email_verification as service
from app.repositories.email_verification_repository import EmailVerificationRepository
from app.services.rate_limit_service import limit_public_auth, limit_verification_peer

router = APIRouter(prefix='/auth/email-verification', tags=['Email verification'])

class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    token: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$', repr=False)

class ResendRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    email: EmailStr

@router.get('/readiness')
def readiness(response: Response, request: Request, db=Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    limit_verification_peer('readiness', request.client.host if request.client else 'unknown')
    try: service.prerequisites(db, require_delivery=False)
    except HTTPException:
        return {'available': False, 'message': 'Email verification is temporarily unavailable.'}
    from app.services.gmail_auth_email import GmailAuthEmailDelivery
    try:
        GmailAuthEmailDelivery()
        delivery_available = True
    except HTTPException:
        delivery_available = False
    return {'available': True, 'delivery_available': delivery_available}

@router.post('/verify')
def verify(data: VerificationRequest, request: Request, response: Response, db=Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    limit_verification_peer('verify', request.client.host if request.client else 'unknown')
    limit_public_auth('email-verification', data.token, request.client.host if request.client else 'unknown')
    service.prerequisites(db, require_delivery=False)
    return service.verify(data.token, EmailVerificationRepository(db))

@router.post('/resend')
def resend(data: ResendRequest, request: Request, response: Response, db=Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    limit_verification_peer('resend', request.client.host if request.client else 'unknown')
    delivery = service.prerequisites(db)
    return service.resend(str(data.email), request.client.host if request.client else 'unknown',
                          EmailVerificationRepository(db), delivery)
