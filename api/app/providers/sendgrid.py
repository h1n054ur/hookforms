"""SendGrid email provider (https://sendgrid.com)."""

import logging
from typing import Optional

import httpx

from app.providers.base import EmailProvider

logger = logging.getLogger(__name__)


class SendGridProvider(EmailProvider):
    """Send transactional email via the SendGrid v3 Mail Send API."""

    @property
    def provider_type(self) -> str:
        return "sendgrid"

    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email

    @classmethod
    def from_config(cls, config: dict) -> "SendGridProvider":
        """
        Config shape: { "api_key": str, "from_email": str }
        """
        return cls(api_key=config["api_key"], from_email=config["from_email"])

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        sender_name: Optional[str] = None,
    ) -> None:
        display_name = sender_name or "HookForms"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": to}]}],
                    "from": {"email": self.from_email, "name": display_name},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}],
                },
            )

            # SendGrid returns 202 on success
            if resp.status_code >= 400:
                raise RuntimeError(f"SendGrid send failed: {resp.status_code} {resp.text}")

        logger.info("Email sent via SendGrid to=%s subject=%s", to, subject)
