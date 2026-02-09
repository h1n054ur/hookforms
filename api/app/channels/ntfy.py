"""Ntfy channel adapter."""

from app.channels import ChannelContext, ChannelPayload


def format_ntfy(config: dict, ctx: ChannelContext) -> ChannelPayload:
    """
    Format a notification for ntfy.sh.
    
    Config expects:
        - url: Ntfy topic URL (e.g., https://ntfy.sh/mytopic)
    """
    url = config.get("url", "")
    
    # Filter out sensitive/internal keys
    skip_keys = {"cf-turnstile-response", "raw", "source"}
    
    # Build plain text message
    lines = []
    for k, v in ctx.body.items():
        if v and k not in skip_keys:
            label = k.replace("_", " ").title()
            lines.append(f"{label}: {v}")
    
    body_text = "\n".join(lines)
    
    return ChannelPayload(
        method="POST",
        url=url,
        headers={
            "Title": f"{ctx.subject_prefix} New Submission",
            "Tags": "incoming_envelope",
            "Priority": "default",
            "X-Forwarded-From": f"hookforms/hooks/{ctx.slug}",
        },
        body=body_text,
    )
