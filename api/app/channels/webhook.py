"""Generic webhook channel adapter."""

import json

from app.channels import ChannelContext, ChannelPayload


def format_webhook(config: dict, ctx: ChannelContext) -> ChannelPayload:
    """
    Format a notification for a generic webhook.
    
    Config expects:
        - url: Webhook URL
        - custom_headers: Optional dict of custom headers
    """
    url = config.get("url", "")
    custom_headers = config.get("custom_headers", {})
    
    # Filter out sensitive/internal keys
    skip_keys = {"cf-turnstile-response", "raw", "source"}
    
    # Build clean body
    clean_body = {k: v for k, v in ctx.body.items() if k not in skip_keys}
    
    # Build headers
    headers = {
        "Content-Type": "application/json",
        "X-Forwarded-From": f"hookforms/hooks/{ctx.slug}",
    }
    
    # Add custom headers if provided
    if isinstance(custom_headers, dict):
        headers.update(custom_headers)
    
    return ChannelPayload(
        method="POST",
        url=url,
        headers=headers,
        body=json.dumps(clean_body),
    )
