"""Pydantic schemas for notification channels and email providers."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Notification Channels
# ---------------------------------------------------------------------------

class ChannelCreate(BaseModel):
    type: str = Field(..., description="Channel type: email, discord, slack, teams, telegram, ntfy, webhook")
    label: Optional[str] = Field(None, description="Optional label for this channel")
    config: dict = Field(..., description="Channel-specific configuration (JSON)")


class ChannelUpdate(BaseModel):
    type: Optional[str] = None
    label: Optional[str] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None


class ChannelResponse(BaseModel):
    id: uuid.UUID
    inbox_id: uuid.UUID
    type: str
    label: Optional[str] = None
    config: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Email Providers
# ---------------------------------------------------------------------------

class EmailProviderUpsert(BaseModel):
    inbox: Optional[str] = Field(None, description="Inbox slug. Omit for global default.")
    type: str = Field(..., description="Provider type: gmail, resend, sendgrid, smtp")
    config: dict = Field(..., description="Provider-specific configuration (JSON)")


class EmailProviderResponse(BaseModel):
    id: uuid.UUID
    inbox_id: Optional[uuid.UUID] = None
    type: str
    config: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
