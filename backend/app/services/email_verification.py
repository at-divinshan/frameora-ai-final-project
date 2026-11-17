"""Email verification needs schema and Redis; sending additionally needs SMTP."""
from typing import Protocol
from hashlib import sha256
from fastapi import HTTPException
from app.services import auth_email_tokens as tokens
from app.services.rate_limit_service import client, limit_public_auth

GENERIC_RESPONSE = {'status': 'accepted', 'message': 'If this account needs verification, an email will be sent.'}

class VerificationAccounts(Protocol):
    def pending_by_email(self, email: str): ...
    def verify_pending(self, *, user_id: int, email_digest: str, auth_version: int) -> bool:
        """Atomically lock/recheck marker, email, version and inactive state; mark verified.

        Return False for missing/already verified/ineligible accounts. Never issue a JWT.
        Do not alter role, password, Google identity, subscriptions or legacy markers.
        """
        ...

def require_verified_for_password_login(account):
    # Call only after a correct password, and only after the approved schema rollout.
    if not hasattr(account, 'email_verification_required'):
        raise HTTPException(503, 'Email verification prerequisites are unavailable.')
    if account.email_verification_required and not account.is_verified:
        raise HTTPException(403, 'Please verify your email before signing in.',
                            headers={'X-Auth-Error': 'EMAIL_VERIFICATION_REQUIRED'})

def send_verification(account, delivery):
    if not getattr(account, 'email_verification_required', False) or account.is_verified:
        return
    token = tokens.issue('verify-email', user_id=account.id, auth_version=account.auth_version, email=account.email)
    try:
        delivery.send(recipient=account.email, purpose='verify-email',
                      link=delivery.config.frontend_origin.rstrip('/') + '/verify-email#token=' + token)
    except Exception:
        # A delivery failure never verifies an account. Best-effort invalidation;
        # even on Redis outage this unused token remains bounded by its TTL.
        try: tokens.consume('verify-email', token)
        except Exception: pass
        raise HTTPException(503, 'Verification email could not be sent. Please request another link.') from None

def resend(email, peer, accounts, delivery):
    email = email.strip().lower()
    limit_public_auth('verification-resend', email, peer)
    try:
        key = 'frameora:verification-cooldown:' + sha256(email.encode()).hexdigest()
        if not client().set(key, '1', nx=True, ex=60):
            raise HTTPException(429, 'Please wait before requesting another email.', headers={'Retry-After':'60'})
    except HTTPException: raise
    except Exception: raise HTTPException(503, 'Verification is temporarily unavailable.') from None
    account = accounts.pending_by_email(email)
    if account is not None:
        try: send_verification(account, delivery)
        except HTTPException: pass  # Same public result for unknown, verified and delivery failure.
    return dict(GENERIC_RESPONSE)

def verify(token, accounts):
    payload = tokens.consume('verify-email', token)
    if not accounts.verify_pending(**payload):
        raise HTTPException(400, 'This link is invalid, expired or already used. Request another link.')
    return {'status': 'verified', 'message': 'Email verified. Please sign in.'}


def prerequisites(db, *, require_delivery=True):
    """Read-only preflight; never silently register an exempt password account."""
    from sqlalchemy import inspect
    from app.models.user import User
    from app.core.account_state import enabled
    from app.services.auth_email_delivery import email_delivery
    try:
        inspector = inspect(db.connection())
        columns = {c['name']: c for c in inspector.get_columns('User')}
        for name in ('email_verification_required', 'is_verified', 'auth_version'):
            if name not in User.__table__.c or name not in columns or columns[name]['nullable']:
                raise ValueError()
        enabled(db)
        delivery = email_delivery() if require_delivery else None
        if client().ping() is not True: raise ValueError()
        return delivery
    except Exception:
        raise HTTPException(503, 'Email verification is temporarily unavailable. Please try again later.') from None
