"""Discord channel adapter."""

import datetime
import json

from app.channels import ChannelContext, ChannelPayload


def format_discord(config: dict, ctx: ChannelContext) -> ChannelPayload:
    """
    Format a notification for Discord webhook.
    
    Config expects:
        - webhook_url: Discord webhook URL
    """
    webhook_url = config.get("webhook_url", "")
    
    # Filter out sensitive/internal keys
    skip_keys = {"cf-turnstile-response", "raw", "source"}
    
    # Build embed fields
    fields = [
        {
            "name": k.replace("_", " ").title(),
            "value": str(v)[:1024],
            "inline": len(str(v)) < 50,
        }
        for k, v in ctx.body.items()
        if v and k not in skip_keys
    ]
    
    # Build Discord embed
    embed_body = {
        "embeds": [
            {
                "title": f"{ctx.subject_prefix} New Submission",
                "color": 0xD4A843,  # Gold color
                "fields": fields,
                "footer": {"text": f"hookforms/hooks/{ctx.slug}"},
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        ]
    }
    
    return ChannelPayload(
        method="POST",
        url=webhook_url,
        headers={
            "Content-Type": "application/json",
            "X-Forwarded-From": f"hookforms/hooks/{ctx.slug}",
        },
        body=json.dumps(embed_body),
    )
