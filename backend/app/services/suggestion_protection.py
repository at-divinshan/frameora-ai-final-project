"""Short-window abuse limits, not a subscription entitlement or permanent quota."""
import secrets
from fastapi import HTTPException
from app.services.rate_limit_service import client
from app.services.oauth_transaction_store import LIMIT

RELEASE = "if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"


def acquire(user_id):
    token=secrets.token_urlsafe(32)
    key=f'frameora:suggestions:inflight:{user_id}'
    try:
        redis=client()
        # Bound total provider cost as well as one account's burst.
        for rate_key,maximum in ((f'frameora:suggestions:rate:{user_id}',6),('frameora:suggestions:global',60)):
            if redis.eval(LIMIT,1,rate_key,300)>maximum:
                raise HTTPException(429,'Too many suggestion requests. Try again later.',headers={'Retry-After':'300'})
        if not redis.set(key,token,nx=True,ex=240):
            raise HTTPException(409,'A suggestion request is already in progress.')
        return key,token
    except HTTPException: raise
    except Exception: raise HTTPException(503,'Suggestions are temporarily unavailable.') from None


def release(lease):
    try: client().eval(RELEASE,1,*lease)
    except Exception: pass  # TTL releases a stranded lease; never replace the original error.
