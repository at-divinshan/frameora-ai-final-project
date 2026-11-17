"""Explicit verification delivery selection; never falls back between providers."""
from dataclasses import dataclass, field
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter
from app.core.config import configuration_values
from app.services.gmail_auth_email import GmailAuthEmailDelivery
from app.services.verification_email_content import SUBJECT, content


@dataclass(frozen=True)
class BrevoSettings:
    api_key: str = field(repr=False)
    sender_email: str
    frontend_origin: str
    sender_name: str = 'Frameora AI'

    def validate(self):
        try:
            origin = urlsplit(self.frontend_origin)
            origin.port
            TypeAdapter(EmailStr).validate_python(self.sender_email)
            if (not self.api_key.strip() or any(c in self.api_key for c in '\r\n')
                or not self.sender_name.strip() or len(self.sender_name) > 200
                or any(c in self.sender_name for c in '\r\n')
                or not origin.hostname or origin.username or origin.password
                or origin.query or origin.fragment or origin.path not in ('', '/')
                or not (origin.scheme == 'https' or origin.scheme == 'http' and origin.hostname in ('localhost', '127.0.0.1', '::1'))):
                raise ValueError()
        except Exception:
            raise HTTPException(503, 'Verification email is unavailable.') from None


class BrevoAuthEmailDelivery:
    def __init__(self, config):
        self.config = config
        config.validate()

    def send(self, *, recipient, purpose, link):
        self.config.validate()
        expected = self.config.frontend_origin.rstrip('/') + '/verify-email#token='
        if purpose != 'verify-email' or not link.startswith(expected) or any(c in recipient for c in '\r\n'):
            raise HTTPException(503, 'Verification email is unavailable.')
        plain, html = content(link)
        try:
            with httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False) as client:
                response = client.post('https://api.brevo.com/v3/smtp/email',
                    headers={'api-key': self.config.api_key, 'Accept': 'application/json'},
                    json={'sender': {'email': self.config.sender_email, 'name': self.config.sender_name},
                          'to': [{'email': recipient}], 'subject': SUBJECT,
                          'textContent': plain, 'htmlContent': html})
                if response.status_code != 201:
                    raise ValueError('Delivery rejected')
        except Exception:
            # Never include provider bodies, recipients, keys or links in errors/logs.
            raise HTTPException(503, 'Verification email could not be sent. Please try again later.') from None


def email_delivery():
    values = configuration_values()
    provider = values.get('EMAIL_DELIVERY_PROVIDER', 'smtp')
    if provider == 'smtp':
        return GmailAuthEmailDelivery()
    if provider == 'brevo':
        return BrevoAuthEmailDelivery(BrevoSettings(
            values.get('BREVO_API_KEY') or '', values.get('BREVO_SENDER_EMAIL') or '',
            values.get('EMAIL_VERIFICATION_FRONTEND_ORIGIN') or '',
            values.get('BREVO_SENDER_NAME', 'Frameora AI')))
    raise HTTPException(503, 'Verification email is unavailable.')
