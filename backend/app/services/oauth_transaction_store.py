"""Encrypted Redis transactions. No fallback store and no import-time connection."""

import json
from functools import lru_cache

from app.core.config import settings
from app.core.google_oidc import digest, new_secret, rejected, unavailable

AUTH_TTL = 300
REGISTRATION_TTL = 600
COMPLETION_TTL = 60
PREFIX = "frameora:oauth:"

# Compare binding and purpose before deletion; an unrelated request cannot burn a transaction.
CONSUME = """
local raw = redis.call('GET', KEYS[1])
if not raw then return false end
local item = cjson.decode(raw)
if item.binding ~= ARGV[1] or item.purpose ~= ARGV[2] then return false end
redis.call('DEL', KEYS[1])
return item.payload
"""
LIMIT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


class TransactionStore:
    def __init__(self):
        from cryptography.fernet import Fernet
        from redis import Redis
        self.cipher = Fernet(settings.oauth_transaction_key.encode("ascii"))
        self.client = Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=3,
            socket_timeout=3, retry_on_timeout=False,
        )

    def put(self, purpose: str, browser: str, data: dict, ttl: int) -> str:
        handle = new_secret()
        try:
            payload = self.cipher.encrypt(json.dumps(data).encode()).decode("ascii")
            envelope = json.dumps({"binding": digest(browser), "purpose": purpose, "payload": payload})
            if not self.client.set(PREFIX + digest(handle), envelope, ex=ttl, nx=True):
                raise ValueError()
            return handle
        except Exception:
            raise unavailable() from None

    def consume(self, handle: str, browser: str, purpose: str) -> dict:
        if not handle or len(handle) > 128 or not browser or len(browser) > 128:
            raise rejected()
        try:
            payload = self.client.eval(CONSUME, 1, PREFIX + digest(handle), digest(browser), purpose)
            if not payload:
                raise LookupError()
            return json.loads(self.cipher.decrypt(payload.encode("ascii"), ttl=REGISTRATION_TTL))
        except LookupError:
            raise rejected() from None
        except Exception:
            raise unavailable() from None

    def limit(self, label: str, maximum: int, seconds: int = 60):
        try:
            count = self.client.eval(LIMIT, 1, PREFIX + "rate:" + digest(label), seconds)
        except Exception:
            raise unavailable() from None
        if count > maximum:
            from fastapi import HTTPException
            raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(seconds)})

    def close(self):
        self.client.close()


@lru_cache(maxsize=1)
def get_store() -> TransactionStore:
    try:
        return TransactionStore()
    except Exception:
        raise unavailable() from None


def close_store():
    if get_store.cache_info().currsize:
        try:
            get_store().close()
        except Exception:
            pass  # Never expose Redis connection configuration on shutdown.
        finally:
            get_store.cache_clear()
