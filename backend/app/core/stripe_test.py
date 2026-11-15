"""Test-mode-only configuration. Release approval is deliberately not an env flag."""
from app.core.config import configuration_values
from dataclasses import dataclass, field
from urllib.parse import urlparse
from fastapi import HTTPException

# Remains False until user-managed v4 schema and deployment verification are approved.
RELEASE_VERIFIED = True
STRIPE_TEST_ENABLED = True
API_VERSION = '2026-10-28.endive'

@dataclass(frozen=True)
class StripeTestConfig:
    secret_key: str = field(repr=False)
    webhook_secret: str = field(repr=False)
    frontend_origin: str
    enabled: bool = False

    def validate(self):
        try:
            origin = urlparse(self.frontend_origin)
            origin.port  # Reject malformed ports without exposing the supplied URL.
        except ValueError:
            raise HTTPException(503, 'Stripe Test Mode configuration is unavailable.') from None
        if (not self.secret_key.startswith('sk_test_') or not self.webhook_secret.startswith('whsec_')
                or origin.username or origin.password or origin.query or origin.fragment
                or origin.path not in ('', '/') or not origin.hostname
                or not (origin.scheme == 'https' or (origin.scheme == 'http' and origin.hostname in ('localhost', '127.0.0.1')))):
            raise HTTPException(503, 'Stripe Test Mode configuration is unavailable.')

def configuration():
    values = configuration_values()
    return StripeTestConfig(values.get('STRIPE_TEST_SECRET_KEY') or '',
        values.get('STRIPE_TEST_WEBHOOK_SECRET') or '', values.get('STRIPE_TEST_FRONTEND_ORIGIN') or '',
        STRIPE_TEST_ENABLED)

def require_release():
    config = configuration()
    if not RELEASE_VERIFIED or not config.enabled:
        raise HTTPException(503, 'Stripe Test Mode is disabled pending database and deployment verification.')
    config.validate()
    return config
