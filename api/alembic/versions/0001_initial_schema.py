"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(12), nullable=True, index=True),
        sa.Column("scopes", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "webhook_inboxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("forward_url", sa.Text, nullable=True),
        sa.Column("notify_email", sa.String(500), nullable=True),
        sa.Column("email_subject_prefix", sa.String(200), nullable=True),
        sa.Column("sender_name", sa.String(200), nullable=True),
        sa.Column("turnstile_secret", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("headers", postgresql.JSON, server_default="{}"),
        sa.Column("body", postgresql.JSON, nullable=True),
        sa.Column("query_params", postgresql.JSON, server_default="{}"),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_webhook_events_inbox_id", "webhook_events", ["inbox_id"])
    op.create_index(
        "ix_webhook_events_received_at", "webhook_events", ["received_at"]
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("webhook_inboxes")
    op.drop_table("api_keys")
