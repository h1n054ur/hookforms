import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WebhookInboxCreate(BaseModel):
    slug: str = Field(..., description="URL-safe inbox name (used in the receive URL)")
    description: Optional[str] = Field(None, description="What this inbox is for")
    forward_url: Optional[str] = Field(None, description="Forward received events to this URL")
    notify_email: Optional[str] = Field(
        None,
        description="Send email notification on every event. Comma-separated for multiple.",
    )
    email_subject_prefix: Optional[str] = Field(
        None, description="Prefix for notification email subjects"
    )
    sender_name: Optional[str] = Field(
        None,
        description="Display name for the email sender (e.g. 'Acme Corp'). Defaults to 'HookForms'.",
    )
    turnstile_secret: Optional[str] = Field(
        None, description="Cloudflare Turnstile secret for bot protection"
    )


class WebhookInboxUpdate(BaseModel):
    description: Optional[str] = None
    forward_url: Optional[str] = None
    notify_email: Optional[str] = None
    email_subject_prefix: Optional[str] = None
    sender_name: Optional[str] = None
    turnstile_secret: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookInboxResponse(BaseModel):
    id: uuid.UUID
    slug: str
    description: Optional[str] = None
    forward_url: Optional[str] = None
    notify_email: Optional[str] = None
    email_subject_prefix: Optional[str] = None
    sender_name: Optional[str] = None
    has_turnstile: bool = Field(False, description="Whether Turnstile verification is configured")
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_inbox(cls, inbox) -> "WebhookInboxResponse":
        resp = cls.model_validate(inbox)
        resp.has_turnstile = bool(inbox.turnstile_secret)
        return resp


class WebhookEventResponse(BaseModel):
    id: uuid.UUID
    method: str
    headers: dict
    body: Optional[dict] = None
    query_params: dict
    source_ip: Optional[str] = None
    received_at: datetime

    model_config = {"from_attributes": True}
