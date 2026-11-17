"""Gmail STARTTLS adapter. No connection occurs until send is explicitly called."""
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from app.services.verification_email_content import SUBJECT, content
import smtplib
import ssl
from urllib.parse import urlsplit
from fastapi import HTTPException
from app.core.config import configuration_values

@dataclass(frozen=True)
class GmailSettings:
    username: str = field(repr=False)
    password: str = field(repr=False)
    frontend_origin: str
    host: str = 'smtp.gmail.com'
    port: int = 587
    timeout: int = 10

    def validate(self):
        origin = urlsplit(self.frontend_origin)
        if (self.host != 'smtp.gmail.com' or self.port != 587 or not 1 <= self.timeout <= 30
                or not self.username or '@' not in self.username or not self.password
                or any(c in self.username for c in '\r\n')
                or origin.username or origin.password or origin.query or origin.fragment
                or origin.path not in ('', '/') or not origin.hostname
                or not (origin.scheme == 'https' or origin.scheme == 'http' and origin.hostname in ('localhost','127.0.0.1','::1'))):
            raise HTTPException(503, 'Verification email is unavailable.')

    @classmethod
    def load(cls):
        values = configuration_values()
        try:
            result = cls(values.get('SMTP_USERNAME') or '', values.get('SMTP_APP_PASSWORD') or '',
                         values.get('EMAIL_VERIFICATION_FRONTEND_ORIGIN') or '',
                         values.get('SMTP_HOST') or 'smtp.gmail.com', int(values.get('SMTP_PORT') or 587),
                         int(values.get('SMTP_TIMEOUT_SECONDS') or 10))
            result.validate()
            return result
        except (ValueError, TypeError):
            raise HTTPException(503, 'Verification email is unavailable.') from None

class GmailAuthEmailDelivery:
    def __init__(self, config=None):
        self.config = config or GmailSettings.load()
        self.config.validate()

    def send(self, *, recipient, purpose, link):
        self.config.validate()
        if purpose != 'verify-email':
            raise HTTPException(503, 'Verification email is unavailable.')
        expected = self.config.frontend_origin.rstrip('/') + '/verify-email#token='
        if not link.startswith(expected) or any(c in recipient for c in '\r\n'):
            raise HTTPException(503, 'Verification email is unavailable.')
        try:
            message = EmailMessage()
            message['Subject'] = SUBJECT
            message['From'] = formataddr(('Frameora AI', self.config.username))
            message['To'] = recipient
            plain, html = content(link)
            message.set_content(plain)
            message.add_alternative(html, subtype='html')
            with smtplib.SMTP(self.config.host, self.config.port, timeout=self.config.timeout) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(self.config.username, self.config.password)
                if smtp.send_message(message):
                    raise ValueError('Delivery rejected')
        except Exception:
            raise HTTPException(503, 'Verification email could not be sent. Please try again later.') from None
