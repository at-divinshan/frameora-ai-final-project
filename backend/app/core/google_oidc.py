"""Google-only OAuth/OIDC boundary. No credentials or provider errors are logged."""

import base64
import hashlib
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException

from app.core.config import settings

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


def unavailable():
    return HTTPException(503, "Google authentication is unavailable. Please try again later.")


def rejected():
    return HTTPException(400, "Google authentication could not be completed. Please start again.")


def require_configuration():
    if not settings.google_auth_enabled:
        raise unavailable()
    if not all((settings.google_client_id, settings.google_client_secret,
                settings.google_redirect_uri, settings.frontend_origin,
                settings.google_completion_url, settings.redis_url,
                settings.oauth_transaction_key)):
        raise unavailable()
    try:
        callback = urlsplit(settings.google_redirect_uri)
        origin = urlsplit(settings.frontend_origin)
        completion = urlsplit(settings.google_completion_url)
        redis = urlsplit(settings.redis_url)
        for url in (callback, origin, completion):
            if not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError()
            if url.scheme != "https":
                if settings.oauth_cookie_secure or url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1"):
                    raise ValueError()
        if origin.path or "*" in origin.netloc or (origin.scheme, origin.netloc) != (completion.scheme, completion.netloc):
            raise ValueError()
        if callback.path != "/auth/google/callback":
            raise ValueError()
        # Disabling Secure is exclusively for loopback development.
        if not settings.oauth_cookie_secure and any(u.hostname not in ("localhost", "127.0.0.1") for u in (callback, origin)):
            raise ValueError()
        if redis.scheme not in ("redis", "rediss") or not redis.hostname:
            raise ValueError()
        if redis.scheme == "redis" and redis.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError()
        from cryptography.fernet import Fernet
        Fernet(settings.oauth_transaction_key.encode("ascii"))
    except Exception:
        raise unavailable() from None


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def authorization_url(state: str, nonce: str, verifier: str) -> str:
    try:
        from authlib.integrations.httpx_client import OAuth2Client
        with OAuth2Client(
            settings.google_client_id, settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri, scope="openid email profile",
            code_challenge_method="S256", timeout=10, trust_env=False,
        ) as client:
            url, _ = client.create_authorization_url(
                AUTHORIZATION_URL, state=state, nonce=nonce,
                code_verifier=verifier, prompt="select_account",
            )
            return url
    except Exception:
        raise unavailable() from None


def exchange_identity(code: str, verifier: str, nonce: str) -> dict:
    try:
        import httpx
        import jwt
        from authlib.integrations.httpx_client import OAuth2Client
        from pydantic import TypeAdapter, EmailStr

        with OAuth2Client(
            settings.google_client_id, settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
            token_endpoint_auth_method="client_secret_post",
            timeout=10, trust_env=False, follow_redirects=False,
        ) as client:
            tokens = client.fetch_token(TOKEN_URL, code=code, code_verifier=verifier)
        encoded = tokens.get("id_token")
        if not isinstance(encoded, str) or len(encoded) > 16384:
            raise ValueError()
        header = jwt.get_unverified_header(encoded)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise ValueError()
        # Fixed trusted key endpoint: never follow jku/x5u from a token header.
        with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
            response = client.get(JWKS_URL)
            response.raise_for_status()
            keys = response.json()["keys"]
        key = next(k for k in keys if k.get("kid") == header["kid"] and k.get("kty") == "RSA" and k.get("use", "sig") == "sig" and k.get("alg", "RS256") == "RS256")
        claims = jwt.decode(
            encoded, jwt.PyJWK.from_dict(key, algorithm="RS256").key,
            algorithms=["RS256"], audience=settings.google_client_id, issuer=ISSUERS,
            options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce", "email", "email_verified"]},
        )
        if not isinstance(claims["nonce"], str) or not secrets.compare_digest(claims["nonce"], nonce):
            raise ValueError()
        audiences = claims["aud"] if isinstance(claims["aud"], list) else [claims["aud"]]
        if (len(audiences) > 1 and "azp" not in claims) or ("azp" in claims and claims["azp"] != settings.google_client_id):
            raise ValueError()
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject or len(subject.encode("utf-8")) > 255:
            raise ValueError()
        if claims["email_verified"] is not True:
            raise ValueError()
        email = str(TypeAdapter(EmailStr).validate_python(claims["email"])).lower()
        if len(email) > 254:
            raise ValueError()
        if "at_hash" in claims:
            access = tokens.get("access_token")
            if not isinstance(access, str):
                raise ValueError()
            expected = base64.urlsafe_b64encode(hashlib.sha256(access.encode("ascii")).digest()[:16]).rstrip(b"=").decode("ascii")
            if not isinstance(claims["at_hash"], str) or not secrets.compare_digest(expected, claims["at_hash"]):
                raise ValueError()
        # Google access/refresh/ID tokens are not persisted or returned.
        return {"sub": subject, "email": email}
    except Exception:
        raise rejected() from None
