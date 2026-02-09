"""Resend email provider (https://resend.com)."""

import logging
from typing import Optional

import httpx

from app.providers.base import EmailProvider

logger = logging.getLogger(__name__)


class ResendProvider(EmailProvider):
    """Send transactional email via the Resend REST API."""

    @property
    def provider_type(self) -> str:
        return "resend"

    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email

    @classmethod
    def from_config(cls, config: dict) -> "ResendProvider":
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
        from_addr = f"{display_name} <{self.from_email}>"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_addr,
                    "to": [to],
                    "subject": subject,
                    "html": html_body,
                },
            )

            if resp.status_code >= 400:
                raise RuntimeError(f"Resend send failed: {resp.status_code} {resp.text}")

        logger.info("Email sent via Resend to=%s subject=%s", to, subject)
