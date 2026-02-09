"""Base types for notification channel adapters."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChannelPayload:
    """Represents the HTTP request payload for a notification channel."""
    method: str
    url: str
    headers: dict[str, str]
    body: str  # JSON string or plain text


@dataclass
class ChannelContext:
    """Context information for formatting notifications."""
    slug: str
    subject_prefix: str
    sender_name: str
    body: dict
