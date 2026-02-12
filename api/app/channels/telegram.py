"""Telegram channel adapter."""

import json

from app.channels import ChannelContext, ChannelPayload
from app.channels.format_value import format_value


def format_telegram(config: dict, ctx: ChannelContext) -> ChannelPayload:
    """
    Format a notification for Telegram bot API.
    
    Config expects:
        - bot_url: Telegram bot API URL (e.g., https://api.telegram.org/bot<TOKEN>/sendMessage)
        - chat_id: Telegram chat ID
    """
    bot_url = config.get("bot_url", "")
    chat_id = config.get("chat_id", "")
    
    # Filter out sensitive/internal keys
    skip_keys = {"cf-turnstile-response", "raw", "source"}
    
    # Build HTML formatted message
    lines = [f"<b>{ctx.subject_prefix} New Submission</b>\n"]
    
    for k, v in ctx.body.items():
        if v and k not in skip_keys:
            label = k.replace("_", " ").title()
            # Escape HTML entities
            value = format_value(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"<b>{label}:</b> {value}")
    
    lines.append(f"\n<i>hookforms/hooks/{ctx.slug}</i>")
    
    text = "\n".join(lines)
    
    # Build Telegram API request body
    telegram_body = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    
    return ChannelPayload(
        method="POST",
        url=bot_url,
        headers={
            "Content-Type": "application/json",
            "X-Forwarded-From": f"hookforms/hooks/{ctx.slug}",
        },
        body=json.dumps(telegram_body),
    )
