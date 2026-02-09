"""Config validation for notification channels and email providers."""

from typing import Optional
from urllib.parse import urlparse

VALID_CHANNEL_TYPES = {"email", "discord", "slack", "teams", "telegram", "ntfy", "webhook"}
VALID_PROVIDER_TYPES = {"gmail", "resend", "sendgrid", "smtp"}

# Common typos -> correct type
_CHANNEL_SUGGESTIONS: dict[str, str] = {
    "discrod": "discord",
    "dicord": "discord",
    "disocrd": "discord",
    "slak": "slack",
    "sclack": "slack",
    "team": "teams",
    "ms-teams": "teams",
    "msteams": "teams",
    "microsoft-teams": "teams",
    "telegarm": "telegram",
    "telgram": "telegram",
    "tg": "telegram",
    "emal": "email",
    "mail": "email",
    "e-mail": "email",
    "webhok": "webhook",
    "hook": "webhook",
    "nfty": "ntfy",
    "notify": "ntfy",
}


def suggest_channel_type(input_type: str) -> Optional[str]:
    """Return a suggestion if the input looks like a typo of a valid type."""
    if input_type in VALID_CHANNEL_TYPES:
        return None
    return _CHANNEL_SUGGESTIONS.get(input_type.lower())


def validate_channel_config(channel_type: str, config: dict) -> Optional[str]:
    """
    Validate channel config for a given type.
    Returns None if valid, or an error message string if invalid.
    """
    validators = {
        "email": _validate_email,
        "discord": _validate_discord,
        "slack": _validate_slack,
        "teams": _validate_teams,
        "telegram": _validate_telegram,
        "ntfy": _validate_ntfy,
        "webhook": _validate_webhook,
    }
    validator = validators.get(channel_type)
    if not validator:
        return f"Unknown channel type: {channel_type}"
    return validator(config)


def validate_provider_config(provider_type: str, config: dict) -> Optional[str]:
    """
    Validate email provider config.
    Returns None if valid, or an error message string if invalid.
    """
    if provider_type == "gmail":
        return _require_fields(config, ["credentials_path", "token_path", "sender_email"])
    elif provider_type == "resend":
        return _require_fields(config, ["api_key", "from_email"])
    elif provider_type == "sendgrid":
        return _require_fields(config, ["api_key", "from_email"])
    elif provider_type == "smtp":
        return _require_fields(config, ["host", "port", "from_email"])
    else:
        return f"Unknown provider type: {provider_type}"


# --- Internal validators ---


def _require_fields(config: dict, fields: list[str]) -> Optional[str]:
    for field in fields:
        if not config.get(field):
            return f"Missing required field: {field}"
    return None


def _validate_url(value, field_name: str) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return f"Missing required field: {field_name}"
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            return f"{field_name} must use http or https protocol"
        if not parsed.netloc:
            return f"{field_name} is not a valid URL"
    except Exception:
        return f"{field_name} is not a valid URL"
    return None


def _validate_email(config: dict) -> Optional[str]:
    recipients = config.get("recipients")
    if not isinstance(recipients, list) or len(recipients) == 0:
        return "Email channel requires a non-empty recipients array"
    for r in recipients:
        if not isinstance(r, str) or "@" not in r:
            return f"Invalid email address: {r}"
    return None


def _validate_discord(config: dict) -> Optional[str]:
    url = config.get("webhook_url") or config.get("url")
    err = _validate_url(url, "webhook_url")
    if err:
        return err
    if isinstance(url, str) and "discord.com/api/webhooks" not in url:
        return "Discord webhook_url must be a discord.com webhook URL"
    return None


def _validate_slack(config: dict) -> Optional[str]:
    url = config.get("webhook_url") or config.get("url")
    err = _validate_url(url, "webhook_url")
    if err:
        return err
    if isinstance(url, str) and "hooks.slack.com/" not in url:
        return "Slack webhook_url must be a hooks.slack.com URL"
    return None


def _validate_teams(config: dict) -> Optional[str]:
    url = config.get("webhook_url") or config.get("url")
    return _validate_url(url, "webhook_url")


def _validate_telegram(config: dict) -> Optional[str]:
    err = _validate_url(config.get("bot_url"), "bot_url")
    if err:
        return err
    if not config.get("chat_id"):
        return "Telegram channel requires chat_id"
    return None


def _validate_ntfy(config: dict) -> Optional[str]:
    err = _validate_url(config.get("url"), "url")
    if err:
        return err
    priority = config.get("priority")
    if priority is not None:
        try:
            p = int(priority)
            if p < 1 or p > 5:
                return "Ntfy priority must be between 1 and 5"
        except (ValueError, TypeError):
            return "Ntfy priority must be between 1 and 5"
    return None


def _validate_webhook(config: dict) -> Optional[str]:
    url = config.get("url") or config.get("webhook_url")
    err = _validate_url(url, "url")
    if err:
        return err
    custom_headers = config.get("custom_headers")
    if custom_headers is not None and not isinstance(custom_headers, dict):
        return "custom_headers must be an object"
    return None
