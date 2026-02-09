"""Resolve the appropriate email provider for a given inbox."""

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import EmailProvider as EmailProviderModel
from app.providers.base import EmailProvider
from app.providers.gmail import GmailProvider
from app.providers.resend import ResendProvider
from app.providers.sendgrid import SendGridProvider
from app.providers.smtp import SmtpProvider

logger = logging.getLogger(__name__)


async def resolve_email_provider(
    db: AsyncSession,
    inbox_id: uuid.UUID,
) -> Optional[EmailProvider]:
    """
    Resolve the email provider for a given inbox.

    Priority:
      1. Inbox-specific provider (email_providers row with matching inbox_id)
      2. Global provider (email_providers row with inbox_id = NULL)
      3. Legacy file-based Gmail (from settings)
      4. None (no email provider available)
    """
    # 1. Try inbox-specific provider
    result = await db.execute(
        select(EmailProviderModel).where(
            EmailProviderModel.inbox_id == inbox_id,
            EmailProviderModel.is_active.is_(True),
        )
    )
    specific = result.scalar_one_or_none()
    if specific:
        return _build_provider(specific)

    # 2. Try global provider (inbox_id is NULL)
    result = await db.execute(
        select(EmailProviderModel).where(
            EmailProviderModel.inbox_id.is_(None),
            EmailProviderModel.is_active.is_(True),
        )
    )
    global_provider = result.scalar_one_or_none()
    if global_provider:
        return _build_provider(global_provider)

    # 3. Legacy file-based Gmail
    return GmailProvider.from_settings()


def _build_provider(record: EmailProviderModel) -> EmailProvider:
    """Instantiate a provider from a database record."""
    config = record.config

    if record.type == "gmail":
        return GmailProvider.from_config(config)
    elif record.type == "resend":
        return ResendProvider.from_config(config)
    elif record.type == "sendgrid":
        return SendGridProvider.from_config(config)
    elif record.type == "smtp":
        return SmtpProvider.from_config(config)
    else:
        raise ValueError(f"Unknown email provider type: {record.type}")
