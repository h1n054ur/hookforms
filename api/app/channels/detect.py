"""Auto-detection of channel type from URL."""


def detect_channel_type(url: str) -> str:
    """
    Detect the channel type from a URL.
    
    Returns:
        Channel type string: 'discord', 'slack', 'teams', 'telegram', 'ntfy', or 'webhook'
    """
    url_lower = url.lower()
    
    if "discord.com/api/webhooks" in url_lower:
        return "discord"
    
    if "hooks.slack.com/" in url_lower:
        return "slack"
    
    if "webhook.office.com" in url_lower or "logic.azure.com" in url_lower:
        return "teams"
    
    if "api.telegram.org/bot" in url_lower:
        return "telegram"
    
    if "ntfy.sh/" in url_lower:
        return "ntfy"
    
    # Default to generic webhook
    return "webhook"
