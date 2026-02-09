"""Notification dispatcher for all channel types."""

import asyncio
import html as html_lib
import logging
from typing import Optional

from app.channels import ChannelContext
from app.channels.detect import detect_channel_type
from app.channels.discord import format_discord
from app.channels.slack import format_slack
from app.channels.teams import format_teams
from app.channels.telegram import format_telegram
from app.channels.ntfy import format_ntfy
from app.channels.webhook import format_webhook
from app.providers.base import EmailProvider
from app.security import safe_http_client

logger = logging.getLogger(__name__)


async def dispatch_notifications(
    inbox,  # WebhookInbox model instance
    channels: list,  # list of NotificationChannel model instances
    body: dict,
    email_provider: Optional[EmailProvider] = None,
) -> None:
    """
    Dispatch notifications to all active channels.
    
    Args:
        inbox: WebhookInbox model instance
        channels: List of NotificationChannel model instances
        body: The webhook body data
        email_provider: Optional resolved EmailProvider instance
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
    
    # Rate-limit email notifications (max 10 per inbox per 10 minutes)
    if email_recipients and email_provider:
        try:
            from app.redis import redis as redis_client
            rate_key = f"channel_email_rate:{inbox.id}"
            email_count = await redis_client.incr(rate_key)
            if email_count == 1:
                await redis_client.expire(rate_key, 600)
            if email_count > 10:
                logger.warning("Email rate limit hit for inbox %s (channel dispatcher)", inbox.slug)
                email_recipients = []  # Skip sending
        except Exception:
            logger.warning("Email rate limiter unavailable for inbox %s", inbox.slug)
    
    # Handle email notifications via resolved provider
    if email_recipients and email_provider:
        await _send_emails(email_provider, email_recipients, ctx, body)


async def _send_emails(
    provider: EmailProvider,
    recipients: list[str],
    ctx: ChannelContext,
    body: dict,
) -> None:
    """Send email notifications to all recipients via the resolved provider."""
    # Build HTML email body
    html_body = _build_email_html(ctx.slug, body, ctx.sender_name)

    name = str(body.get("name", "Unknown"))
    subject_detail = f"from {name}" if name != "Unknown" else "New Submission"
    subject = f"{ctx.subject_prefix} {subject_detail}"

    tasks = []
    for to in recipients:
        tasks.append(_send_single_email(provider, to, subject, html_body, ctx.sender_name))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Failed to send email to %s: %s", recipients[i], result, exc_info=result
                )


async def _send_single_email(
    provider: EmailProvider,
    to: str,
    subject: str,
    html_body: str,
    sender_name: str,
) -> None:
    """Send a single email via the provider."""
    try:
        await provider.send_email(to, subject, html_body, sender_name)
        logger.info("Email sent to %s via %s", to, provider.provider_type)
    except Exception:
        logger.error("Email send failed to %s via %s", to, provider.provider_type, exc_info=True)
        raise


def _build_email_html(slug: str, body: dict, sender_name: str) -> str:
    """Build the HTML email body from form fields."""
    escape = html_lib.escape
    slug_escaped = escape(slug)

    skip_keys = {"raw", "source", "cf-turnstile-response"}
    field_rows = ""
    for key, val in body.items():
        if key in skip_keys or not val:
            continue
        label = escape(key.replace("_", " ").title())
        escaped_val = escape(str(val))
        field_rows += (
            f"<tr>"
            f'<td style="padding:10px 14px;font-weight:600;color:#555;'
            f'white-space:nowrap;vertical-align:top;border-bottom:1px solid #eee;">{label}</td>'
            f'<td style="padding:10px 14px;color:#222;border-bottom:1px solid #eee;">{escaped_val}</td>'
            f"</tr>"
        )

    name = escape(str(body.get("name", "Unknown")))
    email_raw = str(body.get("email", ""))
    email_escaped = escape(email_raw)
    subject_detail = f"from {name}" if name != "Unknown" else "New Submission"
    footer_name = escape(sender_name or "HookForms")

    reply_button = ""
    if email_raw:
        reply_button = (
            f'<tr><td style="padding:0 32px 24px;"><a href="mailto:{email_escaped}" '
            f'style="display:inline-block;padding:10px 20px;background:#1a1a2e;color:#fff;'
            f'text-decoration:none;border-radius:5px;font-size:14px;">Reply to {name}</a></td></tr>'
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:#1a1a2e;padding:24px 32px;">
            <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:600;">{subject_detail}</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 32px;">
            <p style="margin:0 0 16px;color:#666;font-size:14px;">A new form submission was received:</p>
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #eee;border-radius:6px;overflow:hidden;">
              {field_rows}
            </table>
          </td>
        </tr>
        {reply_button}
        <tr>
          <td style="padding:16px 32px;background:#fafafa;border-top:1px solid #eee;">
            <p style="margin:0;color:#999;font-size:12px;">Delivered by {footer_name} &middot; <code style="background:#eee;padding:2px 6px;border-radius:3px;font-size:11px;">/hooks/{slug_escaped}</code></p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


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
