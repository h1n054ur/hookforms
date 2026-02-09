"""Notification dispatcher for all channel types."""

import asyncio
import logging

from app.channels import ChannelContext
from app.channels.detect import detect_channel_type
from app.channels.discord import format_discord
from app.channels.slack import format_slack
from app.channels.teams import format_teams
from app.channels.telegram import format_telegram
from app.channels.ntfy import format_ntfy
from app.channels.webhook import format_webhook
from app.security import safe_http_client

logger = logging.getLogger(__name__)


async def dispatch_notifications(
    inbox,  # WebhookInbox model instance
    channels: list,  # list of NotificationChannel model instances
    body: dict,
    email_provider=None,  # EmailProvider model instance or None
) -> None:
    """
    Dispatch notifications to all active channels.
    
    Args:
        inbox: WebhookInbox model instance
        channels: List of NotificationChannel model instances
        body: The webhook body data
        email_provider: Optional EmailProvider model instance
    """
    # Build context for all adapters
    ctx = ChannelContext(
        slug=inbox.slug,
        subject_prefix=inbox.email_subject_prefix or f"[{inbox.slug}]",
        sender_name=inbox.sender_name or "HookForms",
        body=body,
    )
    
    # Collect tasks for async dispatch
    tasks = []
    email_recipients = []
    
    for channel in channels:
        if not channel.is_active:
            continue
        
        try:
            channel_type = channel.type
            
            # Auto-detect if type is 'webhook'
            if channel_type == "webhook":
                url = channel.config.get("url", "")
                if url:
                    detected_type = detect_channel_type(url)
                    if detected_type != "webhook":
                        channel_type = detected_type
            
            # Get the appropriate formatter
            if channel_type == "discord":
                payload = format_discord(channel.config, ctx)
            elif channel_type == "slack":
                payload = format_slack(channel.config, ctx)
            elif channel_type == "teams":
                payload = format_teams(channel.config, ctx)
            elif channel_type == "telegram":
                payload = format_telegram(channel.config, ctx)
            elif channel_type == "ntfy":
                payload = format_ntfy(channel.config, ctx)
            elif channel_type == "webhook":
                payload = format_webhook(channel.config, ctx)
            elif channel_type == "email":
                # Collect email recipients for later processing
                recipients = channel.config.get("recipients", [])
                if isinstance(recipients, str):
                    recipients = [r.strip() for r in recipients.split(",") if r.strip()]
                email_recipients.extend(recipients)
                continue
            else:
                logger.warning(f"Unknown channel type: {channel_type}")
                continue
            
            # Create async task for HTTP request
            tasks.append(_send_notification(payload, channel.id))
            
        except Exception as e:
            logger.error(f"Error preparing notification for channel {channel.id}: {e}", exc_info=True)
    
    # Fire all HTTP notifications concurrently
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle email notifications
    if email_recipients and email_provider and email_provider.is_active:
        logger.info(f"Would send email to {len(email_recipients)} recipients via provider {email_provider.type}")
        # TODO: Implement actual email provider integration
        # For now, just log that we would send emails


async def _send_notification(payload, channel_id) -> None:
    """
    Send a single notification via HTTP.
    
    Args:
        payload: ChannelPayload instance
        channel_id: Channel ID for logging
    """
    try:
        async with safe_http_client(timeout=10) as client:
            response = await client.request(
                method=payload.method,
                url=payload.url,
                headers=payload.headers,
                content=payload.body,
            )
            
            if response.status_code >= 400:
                logger.warning(
                    f"Channel {channel_id} returned status {response.status_code}: {response.text[:200]}"
                )
            else:
                logger.debug(f"Successfully sent notification to channel {channel_id}")
                
    except Exception as e:
        logger.error(f"Failed to send notification to channel {channel_id}: {e}", exc_info=True)
