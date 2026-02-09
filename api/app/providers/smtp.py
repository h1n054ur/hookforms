"""SMTP email provider (generic, works with any SMTP server)."""

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from functools import partial
from typing import Optional

from app.providers.base import EmailProvider

logger = logging.getLogger(__name__)


class SmtpProvider(EmailProvider):
    """Send email via a standard SMTP server."""

    @property
    def provider_type(self) -> str:
        return "smtp"

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool,
        from_email: str,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.from_email = from_email

    @classmethod
    def from_config(cls, config: dict) -> "SmtpProvider":
        """
        Config shape: {
            "host": str,
            "port": int,
            "username": str,
            "password": str,
            "use_tls": bool,
            "from_email": str,
        }
        """
        return cls(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            use_tls=config.get("use_tls", True),
            from_email=config["from_email"],
        )

    def _send_sync(
        self,
        to: str,
        subject: str,
        html_body: str,
        sender_name: Optional[str] = None,
    ) -> None:
        """Synchronous SMTP send."""
        display_name = sender_name or "HookForms"

        msg = MIMEText(html_body, "html")
        msg["Subject"] = subject
        msg["From"] = f"{display_name} <{self.from_email}>"
        msg["To"] = to

        if self.use_tls:
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port) as server:
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(msg)

        logger.info("Email sent via SMTP to=%s subject=%s", to, subject)

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        sender_name: Optional[str] = None,
    ) -> None:
        """Send email asynchronously by running sync SMTP in executor."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(self._send_sync, to, subject, html_body, sender_name),
        )
