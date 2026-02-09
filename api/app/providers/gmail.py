"""Gmail email provider using OAuth2 credentials."""

import asyncio
import base64
import logging
from email.mime.text import MIMEText
from functools import partial
from pathlib import Path
from typing import Optional

from app.providers.base import EmailProvider

logger = logging.getLogger(__name__)


class GmailProvider(EmailProvider):
    """
    Gmail provider that uses Google API client with file-based OAuth2 tokens.
    This is the legacy/default provider for the self-hosted version.
    """

    @property
    def provider_type(self) -> str:
        return "gmail"

    def __init__(
        self,
        credentials_path: str,
        token_path: str,
        sender_email: str,
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.sender_email = sender_email

    @classmethod
    def from_settings(cls) -> Optional["GmailProvider"]:
        """Create a GmailProvider from app settings. Returns None if not configured."""
        from app.config import settings

        token_path = Path(settings.gmail_token_path)
        if not token_path.exists():
            logger.warning("Gmail token not found at %s", token_path)
            return None
        if not settings.gmail_sender_email:
            logger.warning("GMAIL_SENDER_EMAIL not set")
            return None

        return cls(
            credentials_path=settings.gmail_credentials_path,
            token_path=settings.gmail_token_path,
            sender_email=settings.gmail_sender_email,
        )

    @classmethod
    def from_config(cls, config: dict) -> "GmailProvider":
        """
        Create a GmailProvider from stored config (email_providers table).

        Config shape: {
            "credentials_path": str,
            "token_path": str,
            "sender_email": str,
        }
        """
        import os
        
        allowed_dir = "/app/config/gmail"
        for key in ("credentials_path", "token_path"):
            path = os.path.realpath(config[key])
            if not path.startswith(allowed_dir):
                raise ValueError(
                    f"Gmail {key} must be under {allowed_dir}, got: {path}"
                )
        
        return cls(
            credentials_path=config["credentials_path"],
            token_path=config["token_path"],
            sender_email=config["sender_email"],
        )

    def _get_credentials(self):
        """Get and refresh Google OAuth2 credentials (synchronous)."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        scopes = ["https://www.googleapis.com/auth/gmail.send"]
        token_path = Path(self.token_path)

        if not token_path.exists():
            raise RuntimeError(
                f"Gmail token not found at {token_path}. "
                "Run 'python scripts/gmail_auth.py' to authorize."
            )

        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

        if creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Gmail token")
            creds.refresh(Request())
            token_path.write_text(creds.to_json())

        if not creds.valid:
            raise RuntimeError("Gmail credentials are invalid. Re-run gmail_auth.py.")

        return creds

    def _send_sync(
        self,
        to: str,
        subject: str,
        html_body: str,
        sender_name: Optional[str] = None,
    ) -> None:
        """Synchronous send via Google API client."""
        from googleapiclient.discovery import build

        creds = self._get_credentials()
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        display_name = sender_name or "HookForms"
        msg = MIMEText(html_body, "html")
        msg["to"] = to
        msg["from"] = f"{display_name} <{self.sender_email}>"
        msg["subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        logger.info("Email sent: id=%s to=%s subject=%s", result.get("id"), to, subject)

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        sender_name: Optional[str] = None,
    ) -> None:
        """Send email asynchronously by running sync Gmail API in executor."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(self._send_sync, to, subject, html_body, sender_name),
        )
