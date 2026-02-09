"""Base email provider interface."""

from abc import ABC, abstractmethod
from typing import Optional


class EmailProvider(ABC):
    """
    Common interface for all email providers.
    Each provider implements send_email() using its own API/protocol.
    """

    @property
    @abstractmethod
    def provider_type(self) -> str:
        ...

    @abstractmethod
    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        sender_name: Optional[str] = None,
    ) -> None:
        """Send an HTML email to a single recipient."""
        ...
