"""Argon2 password hashing and strictly validated access tokens."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from secrets import token_urlsafe

import jwt
from fastapi import HTTPException
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import settings


password_hasher = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "frameora-api"
JWT_AUDIENCE = "frameora-frontend"


def require_jwt_configuration() -> str:
    secret = settings.jwt_secret_key
    if len(secret.strip().encode("utf-8")) < 32:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured. Contact the application administrator.",
        )
    return secret


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    # Used for unknown accounts so login still performs Argon2 verification.
    return hash_password(token_urlsafe(32))


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        # Do the same expensive work without inventing a stored account password.
        valid = password_hasher.verify(password, password_hash or dummy_password_hash())
        return bool(password_hash) and valid
    except (UnknownHashError, ValueError, TypeError):
        return False


def auth_versions_enabled() -> bool:
    return settings.auth_version_enabled


def require_password_management():
    if not auth_versions_enabled() or not settings.password_management_enabled:
        raise HTTPException(503, "Password management is not enabled.")


def create_access_token(user_id: str, remember_me: bool, auth_version: int | None = None) -> tuple[str, int]:
    secret = require_jwt_configuration()
    now = datetime.now(timezone.utc)
    lifetime = (
        timedelta(days=settings.jwt_remember_me_expire_days)
        if remember_me
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    claims = {
            "sub": str(user_id), "iat": now, "nbf": now, "exp": now + lifetime,
            "iss": JWT_ISSUER, "aud": JWT_AUDIENCE, "type": "access",
        }
    if auth_versions_enabled():
        if type(auth_version) is not int or not 0 <= auth_version <= 2**64 - 1:
            raise HTTPException(503, "Authentication is unavailable.")
        claims["auth_version"] = auth_version
        # Distinguish separately issued sessions even within the same second.
        claims["jti"] = token_urlsafe(24)
    token = jwt.encode(
        claims,
        secret,
        algorithm=JWT_ALGORITHM,
    )
    return token, int(lifetime.total_seconds())


def decode_access_claims(token: str) -> dict:
    secret = require_jwt_configuration()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["sub", "iat", "nbf", "exp", "iss", "aud", "type"]},
        )
        if payload["type"] != "access" or not isinstance(payload["sub"], str) or not payload["sub"]:
            raise jwt.InvalidTokenError()
        if auth_versions_enabled() and (type(payload.get("auth_version")) is not int or
                                       not 0 <= payload["auth_version"] <= 2**64 - 1):
            raise jwt.InvalidTokenError()
        return payload
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
        raise HTTPException(
            status_code=401,
            detail="Your session is invalid or has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def decode_access_token(token: str) -> str:
    return decode_access_claims(token)["sub"]
