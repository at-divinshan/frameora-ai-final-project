"""Redis limits independent of Google configuration. No in-memory fallback."""

from functools import lru_cache
import hashlib
from urllib.parse import urlsplit

from fastapi import HTTPException
from redis import Redis

from app.core.config import settings
from app.services.oauth_transaction_store import LIMIT


@lru_cache(maxsize=1)
def client():
    url = urlsplit(settings.redis_url)
    if url.scheme not in ("redis", "rediss") or not url.hostname or (
        url.scheme == "redis" and url.hostname not in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError()
    return Redis.from_url(settings.redis_url, decode_responses=True,
                          socket_connect_timeout=3, socket_timeout=3, retry_on_timeout=False)


def limit_password_attempt(action: str, user_id: int, peer: str):
    try:
        redis = client()
        for label, maximum in ((f"{action}:account:{user_id}", 5), (f"password:peer:{peer}", 30)):
            key = "frameora:password-rate:" + hashlib.sha256(label.encode()).hexdigest()
            if redis.eval(LIMIT, 1, key, 300) > maximum:
                raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": "300"})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Password management is temporarily unavailable.") from None


def close_rate_limits():
    if client.cache_info().currsize:
        try:
            client().close()
        except Exception:
            pass
        finally:
            client.cache_clear()
