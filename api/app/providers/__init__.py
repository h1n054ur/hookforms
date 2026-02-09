"""Email provider abstraction layer."""

from app.providers.base import EmailProvider
from app.providers.gmail import GmailProvider
from app.providers.resend import ResendProvider
from app.providers.sendgrid import SendGridProvider
from app.providers.smtp import SmtpProvider
from app.providers.resolver import resolve_email_provider

__all__ = [
    "EmailProvider",
    "GmailProvider",
    "ResendProvider",
    "SendGridProvider",
    "SmtpProvider",
    "resolve_email_provider",
]
