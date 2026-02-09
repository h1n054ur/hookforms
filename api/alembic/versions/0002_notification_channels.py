"""Add notification_channels and email_providers tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.String(50),
            nullable=False,
            comment="email, discord, slack, teams, telegram, ntfy, webhook",
        ),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("config", postgresql.JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_notification_channels_inbox_id", "notification_channels", ["inbox_id"])
    op.create_index("ix_notification_channels_type", "notification_channels", ["type"])

    op.create_table(
        "email_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_inboxes.id", ondelete="CASCADE"),
            nullable=True,
            unique=True,
            comment="NULL = global default provider",
        ),
        sa.Column(
            "type",
            sa.String(50),
            nullable=False,
            comment="gmail, resend, sendgrid, smtp",
        ),
        sa.Column("config", postgresql.JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("email_providers")
    op.drop_table("notification_channels")
