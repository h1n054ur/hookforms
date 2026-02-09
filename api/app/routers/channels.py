"""CRUD routes for notification channels and email providers."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_scope
from app.channels.detect import detect_channel_type
from app.channels.validate import (
    validate_channel_config,
    validate_provider_config,
    suggest_channel_type,
)
from app.config import settings
from app.database import get_db
from app.models.notification import NotificationChannel, EmailProvider
from app.models.webhook import WebhookInbox
from app.response import single_response
from app.schemas.channel import (
    ChannelCreate,
    ChannelUpdate,
    ChannelResponse,
    EmailProviderUpsert,
    EmailProviderResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hooks", tags=["channels"])

VALID_CHANNEL_TYPES = {"email", "discord", "slack", "teams", "telegram", "ntfy", "webhook"}
VALID_PROVIDER_TYPES = {"gmail", "resend", "sendgrid", "smtp"}


# ---------------------------------------------------------------------------
# Helper: resolve inbox by slug
# ---------------------------------------------------------------------------

async def _get_inbox(slug: str, db: AsyncSession) -> WebhookInbox:
    result = await db.execute(select(WebhookInbox).where(WebhookInbox.slug == slug))
    inbox = result.scalar_one_or_none()
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")
    return inbox


# ---------------------------------------------------------------------------
# Channel CRUD
# ---------------------------------------------------------------------------

@router.post("/inboxes/{slug}/channels", status_code=201, summary="Add a notification channel")
async def create_channel(
    slug: str,
    body: ChannelCreate,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    inbox = await _get_inbox(slug, db)

    channel_type = body.type
    if channel_type not in VALID_CHANNEL_TYPES:
        suggestion = suggest_channel_type(channel_type)
        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
        raise HTTPException(status_code=400, detail=f"Invalid channel type: {channel_type}.{hint}")

    # Auto-detect webhook URL type (check both 'url' and 'webhook_url' keys)
    if channel_type == "webhook":
        url = body.config.get("url") or body.config.get("webhook_url")
        if isinstance(url, str):
            detected = detect_channel_type(url)
            if detected != "webhook":
                channel_type = detected

    # Validate config for the resolved channel type
    config_error = validate_channel_config(channel_type, body.config)
    if config_error:
        raise HTTPException(status_code=400, detail=config_error)

    channel = NotificationChannel(
        inbox_id=inbox.id,
        type=channel_type,
        label=body.label,
        config=body.config,
        is_active=True,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)

    return single_response(ChannelResponse.model_validate(channel))


@router.get("/inboxes/{slug}/channels", summary="List notification channels")
async def list_channels(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    inbox = await _get_inbox(slug, db)

    result = await db.execute(
        select(NotificationChannel)
        .where(NotificationChannel.inbox_id == inbox.id)
        .order_by(NotificationChannel.created_at.desc())
    )
    items = [ChannelResponse.model_validate(ch) for ch in result.scalars().all()]
    return {"data": items}


@router.patch("/inboxes/{slug}/channels/{channel_id}", summary="Update a notification channel")
async def update_channel(
    slug: str,
    channel_id: str,
    body: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    inbox = await _get_inbox(slug, db)

    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.inbox_id == inbox.id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    update_data = body.model_dump(exclude_unset=True)
    if "type" in update_data:
        if update_data["type"] not in VALID_CHANNEL_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid channel type: {update_data['type']}")

    for field, value in update_data.items():
        setattr(channel, field, value)

    await db.commit()
    await db.refresh(channel)

    return single_response(ChannelResponse.model_validate(channel))


@router.delete("/inboxes/{slug}/channels/{channel_id}", status_code=204, summary="Remove a notification channel")
async def delete_channel(
    slug: str,
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    inbox = await _get_inbox(slug, db)

    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.inbox_id == inbox.id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    await db.delete(channel)
    await db.commit()


# ---------------------------------------------------------------------------
# Email provider config
# ---------------------------------------------------------------------------

@router.get("/config/email-provider", summary="Get email provider config", tags=["email-providers"])
async def get_email_provider(
    inbox: str = Query(None, description="Inbox slug (omit for global)"),
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    inbox_id = None
    if inbox:
        inbox_obj = await _get_inbox(inbox, db)
        inbox_id = inbox_obj.id

    if inbox_id:
        result = await db.execute(
            select(EmailProvider).where(
                EmailProvider.inbox_id == inbox_id,
                EmailProvider.is_active.is_(True),
            )
        )
    else:
        result = await db.execute(
            select(EmailProvider).where(
                EmailProvider.inbox_id.is_(None),
                EmailProvider.is_active.is_(True),
            )
        )

    provider = result.scalar_one_or_none()

    if not provider:
        # Check if legacy file-based Gmail is available
        has_env_gmail = (
            Path(settings.gmail_token_path).exists()
            and bool(settings.gmail_sender_email)
        )
        return {"data": None, "meta": {"fallback": "env_gmail" if has_env_gmail else None}}

    return {"data": EmailProviderResponse.model_validate(provider)}


@router.put("/config/email-provider", summary="Set email provider config", tags=["email-providers"])
async def set_email_provider(
    body: EmailProviderUpsert,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    if body.type not in VALID_PROVIDER_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {body.type}")

    # Validate provider config
    provider_error = validate_provider_config(body.type, body.config)
    if provider_error:
        raise HTTPException(status_code=400, detail=provider_error)

    inbox_id = None
    if body.inbox:
        inbox_obj = await _get_inbox(body.inbox, db)
        inbox_id = inbox_obj.id

    # Delete existing provider for this scope
    if inbox_id:
        await db.execute(
            delete(EmailProvider).where(EmailProvider.inbox_id == inbox_id)
        )
    else:
        await db.execute(
            delete(EmailProvider).where(EmailProvider.inbox_id.is_(None))
        )

    provider = EmailProvider(
        inbox_id=inbox_id,
        type=body.type,
        config=body.config,
        is_active=True,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    return {"data": EmailProviderResponse.model_validate(provider)}


@router.delete("/config/email-provider", status_code=204, summary="Remove email provider config", tags=["email-providers"])
async def delete_email_provider(
    inbox: str = Query(None, description="Inbox slug (omit for global)"),
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    if inbox:
        inbox_obj = await _get_inbox(inbox, db)
        await db.execute(
            delete(EmailProvider).where(EmailProvider.inbox_id == inbox_obj.id)
        )
    else:
        await db.execute(
            delete(EmailProvider).where(EmailProvider.inbox_id.is_(None))
        )
    await db.commit()
