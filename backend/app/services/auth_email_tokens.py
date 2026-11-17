"""Purpose-bound, single-use Redis tokens for future email workflows.

Not wired to registration until schema rollout and delivery are approved.
Only token digests are persisted; callers must never return or log raw tokens.
"""
import hashlib
import json
import re
import secrets
from fastapi import HTTPException
from app.services.rate_limit_service import client

TTLS = {'verify-email': 1800}
CONSUME = "local v=redis.call('GET',KEYS[1]); if v then redis.call('DEL',KEYS[1]); end; return v"


def key(purpose, token):
    if purpose not in TTLS: raise ValueError('Unsupported email token purpose')
    return 'frameora:email-token:'+purpose+':'+hashlib.sha256(token.encode()).hexdigest()


def issue(purpose, *, user_id, auth_version, email):
    if purpose not in TTLS: raise ValueError('Unsupported email token purpose')
    token=secrets.token_urlsafe(32)
    payload=json.dumps({'user_id':user_id,'auth_version':auth_version,
                        'email_digest':hashlib.sha256(email.strip().lower().encode()).hexdigest()})
    try:
        if not client().set(key(purpose,token),payload,nx=True,ex=TTLS[purpose]): raise ValueError()
    except Exception:
        raise HTTPException(503,'Email authentication is temporarily unavailable.') from None
    return token


def consume(purpose, token):
    if purpose not in TTLS: raise ValueError('Unsupported email token purpose')
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):
        raise HTTPException(400,'This link is invalid or expired.')
    try:
        raw=client().eval(CONSUME,1,key(purpose,token))
        if raw is None: raise HTTPException(400,'This link is invalid or expired.')
        return json.loads(raw)
    except HTTPException: raise
    except Exception: raise HTTPException(503,'Email authentication is temporarily unavailable.') from None
