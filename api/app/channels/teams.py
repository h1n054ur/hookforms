"""Microsoft Teams channel adapter."""

import datetime
import json

from app.channels import ChannelContext, ChannelPayload


def format_teams(config: dict, ctx: ChannelContext) -> ChannelPayload:
    """
    Format a notification for Microsoft Teams webhook using Adaptive Cards.
    
    Config expects:
        - webhook_url: Teams webhook URL
    """
    webhook_url = config.get("webhook_url", "")
    
    # Filter out sensitive/internal keys
    skip_keys = {"cf-turnstile-response", "raw", "source"}
    
    # Build FactSet for Adaptive Card
    facts = [
        {
            "title": k.replace("_", " ").title(),
            "value": str(v)[:1024],
        }
        for k, v in ctx.body.items()
        if v and k not in skip_keys
    ]
    
    # Build Adaptive Card
    adaptive_card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"{ctx.subject_prefix} New Submission",
                "weight": "Bolder",
                "size": "Large",
                "wrap": True,
            },
            {
                "type": "FactSet",
                "facts": facts,
            },
            {
                "type": "TextBlock",
                "text": f"hookforms/hooks/{ctx.slug}",
                "size": "Small",
                "color": "Accent",
                "wrap": True,
            },
        ],
    }
    
    # Wrap in Teams message format
    teams_body = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": adaptive_card,
            }
        ],
    }
    
    return ChannelPayload(
        method="POST",
        url=webhook_url,
        headers={
            "Content-Type": "application/json",
            "X-Forwarded-From": f"hookforms/hooks/{ctx.slug}",
        },
        body=json.dumps(teams_body),
    )
