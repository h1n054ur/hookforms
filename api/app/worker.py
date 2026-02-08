"""ARQ background worker — event cleanup cron."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import delete as sa_delete

from app.config import settings
from app.database import async_session
from app.models.webhook import WebhookEvent

logger = logging.getLogger(__name__)


async def cleanup_old_webhook_events(ctx: dict[str, Any]) -> None:
    """Delete webhook events older than the configured retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.event_retention_days)
    async with async_session() as db:
        result = await db.execute(
            sa_delete(WebhookEvent).where(WebhookEvent.received_at < cutoff)
        )
        if result.rowcount:
            logger.info("Cleaned up %d old webhook events", result.rowcount)
        await db.commit()


def parse_redis_url(url: str) -> RedisSettings:
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password or None,
        database=int(parsed.path.lstrip("/") or 0),
    )


class WorkerSettings:
    functions = []
    cron_jobs = [
        cron(cleanup_old_webhook_events, hour={3}, minute={0}),
    ]
    redis_settings = parse_redis_url(settings.redis_url)
