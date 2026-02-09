"""Slack channel adapter."""

import json

from app.channels import ChannelContext, ChannelPayload


def format_slack(config: dict, ctx: ChannelContext) -> ChannelPayload:
    """
    Format a notification for Slack webhook.
    
    Config expects:
        - webhook_url: Slack webhook URL
    """
    webhook_url = config.get("webhook_url", "")
    
    # Filter out sensitive/internal keys
    skip_keys = {"cf-turnstile-response", "raw", "source"}
    
    # Build mrkdwn formatted lines
    lines = [
        f"*{k.replace('_', ' ')}:* {v}"
        for k, v in ctx.body.items()
        if v and k not in skip_keys
    ]
    
    # Build Slack message with blocks
    slack_body = {
        "text": f"{ctx.subject_prefix} New Submission",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines)},
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
        body=json.dumps(slack_body),
    )
