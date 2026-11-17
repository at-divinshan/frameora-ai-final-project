"""Current-token revocation only. Redis contains digests, never bearer tokens."""
from hashlib import sha256
from base64 import urlsafe_b64decode
from fastapi import HTTPException
from app.services.rate_limit_service import client


def key(token):
    # Normalize signature encoding: equivalent base64 padding must not evade revocation.
    header, payload, signature = token.split('.')
    signature_bytes = urlsafe_b64decode(signature + '=' * (-len(signature) % 4))
    identifier = (header + '.' + payload).encode('ascii') + b'.' + signature_bytes
    return 'frameora:revoked-jwt:' + sha256(identifier).hexdigest()


def require_not_revoked(token):
    try:
        revoked = client().exists(key(token))
    except Exception:
        raise HTTPException(503, 'Session verification is temporarily unavailable.') from None
    if revoked:
        raise HTTPException(401, 'Your session has ended. Please sign in again.',
                            headers={'WWW-Authenticate': 'Bearer'})


def revoke(token, claims):
    try:
        # Absolute expiry prevents retries or latency from extending token retention.
        if not client().set(key(token), '1', pxat=int(claims['exp']) * 1000):
            raise ValueError()
    except Exception:
        raise HTTPException(503, 'Server logout could not be confirmed.') from None
