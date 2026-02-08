"""Gmail API helper — send email using OAuth2 refresh token."""

import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]


def _get_credentials() -> Credentials:
    token_path = Path(settings.gmail_token_path)
    if not token_path.exists():
        raise RuntimeError(
            f"Gmail token not found at {token_path}. "
            "Run 'python scripts/gmail_auth.py' to authorize."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds.expired and creds.refresh_token:
        logger.info("Refreshing expired Gmail token")
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    if not creds.valid:
        raise RuntimeError("Gmail credentials are invalid. Re-run gmail_auth.py.")

    return creds


def _get_service():
    creds = _get_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def send_email(
    to: str,
    subject: str,
    body: str,
    html: bool = False,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    sender_name: Optional[str] = None,
) -> dict:
    """Send an email via Gmail API. Returns the Gmail API response."""
    service = _get_service()
    sender = settings.gmail_sender_email
    display_name = sender_name or "HookForms"

    if html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "html"))
    else:
        msg = MIMEText(body, "plain")

    msg["to"] = to
    msg["from"] = f"{display_name} <{sender}>"
    msg["subject"] = subject

    if cc:
        msg["cc"] = cc
    if bcc:
        msg["bcc"] = bcc

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )

    logger.info("Email sent: id=%s to=%s subject=%s", result.get("id"), to, subject)
    return result
