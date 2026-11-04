"""Fixed OAuth failure events only: never include request or exception contents."""

from functools import wraps
import logging

logger = logging.getLogger(__name__)
EVENTS = frozenset({
    "configuration", "origin", "content_type", "browser_binding",
    "callback_parameters", "callback_failed", "callback_processing",
    "authorization_url", "token_exchange", "id_token_header", "jwks_fetch",
    "id_token_validation", "nonce_validation", "identity_claims", "access_token_hash",
    "transaction_write", "transaction_input", "transaction_no_match",
    "transaction_read", "transaction_decrypt", "completion_account_or_jwt",
})


def failure(event: str):
    # Even a future accidental caller passing provider text cannot print it.
    logger.warning("Google OAuth failure stage=%s", event if event in EVENTS else "unknown")


def diagnosed(event: str):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except Exception:
                failure(event)
                raise
        return wrapped
    return decorate
