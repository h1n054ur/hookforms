import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_VALID_SCOPES = {"webhooks", "admin"}


class ApiKeyCreate(BaseModel):
    name: str = Field(..., max_length=100, description="Descriptive name for this key")
    scopes: list[str] = Field(
        default=[],
        description="Allowed scopes: webhooks, admin",
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        invalid = set(v) - _VALID_SCOPES
        if invalid:
            raise ValueError(
                f"Invalid scopes: {', '.join(sorted(invalid))}. "
                f"Valid: {', '.join(sorted(_VALID_SCOPES))}"
            )
        return v


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    scopes: list[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyResponse):
    raw_key: str = Field(..., description="Save this key — it cannot be retrieved again")
