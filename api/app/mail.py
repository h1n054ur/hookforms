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

# Module-level cache for credentials and Gmail service to avoid
# re-reading token files and rebuilding the API client on every send.
_cached_creds: Optional[Credentials] = None
_cached_service = None


def _get_credentials() -> Credentials:
    global _cached_creds

    # Return cached creds if still valid
    if _cached_creds and _cached_creds.valid:
        return _cached_creds

    token_path = Path(settings.gmail_token_path)
    if not token_path.exists():
        raise RuntimeError(
            f"Gmail token not found at {token_path}. "
            "Run 'python scripts/gmail_auth.py' to authorize."
        )

    # Re-read from file if no cache or if cached creds can't be refreshed
    if _cached_creds is None:
        _cached_creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if _cached_creds.expired and _cached_creds.refresh_token:
        logger.info("Refreshing expired Gmail token")
        _cached_creds.refresh(Request())
        token_path.write_text(_cached_creds.to_json())

    if not _cached_creds.valid:
        # Force re-read from file in case it was updated externally
        _cached_creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if _cached_creds.expired and _cached_creds.refresh_token:
            _cached_creds.refresh(Request())
            token_path.write_text(_cached_creds.to_json())
        if not _cached_creds.valid:
            raise RuntimeError("Gmail credentials are invalid. Re-run gmail_auth.py.")

    return _cached_creds


def _get_service():
    global _cached_service

    creds = _get_credentials()

    # Rebuild service if credentials changed or first call
    if _cached_service is None:
        _cached_service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    return _cached_service


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
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()

    logger.info("Email sent: id=%s to=%s subject=%s", result.get("id"), to, subject)
    return result
