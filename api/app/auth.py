import logging
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from passlib.hash import pbkdf2_sha256
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

ALL_SCOPES = ["webhooks", "admin"]

_LOCKOUT_THRESHOLD = 10
_LOCKOUT_WINDOW = 300  # 5 minutes


def _get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check_lockout(ip: str) -> None:
    from app.redis import redis as redis_client

    try:
        count = await redis_client.get(f"auth_fail:{ip}")
        if count and int(count) >= _LOCKOUT_THRESHOLD:
            raise HTTPException(
                status_code=429,
                detail="Too many failed authentication attempts. Try again later.",
            )
    except HTTPException:
        raise
    except Exception:
        pass


async def _record_failure(ip: str) -> None:
    from app.redis import redis as redis_client

    try:
        key = f"auth_fail:{ip}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, _LOCKOUT_WINDOW)
    except Exception:
        pass


async def _clear_failure(ip: str) -> None:
    from app.redis import redis as redis_client

    try:
        await redis_client.delete(f"auth_fail:{ip}")
    except Exception:
        pass


def hash_key(key: str) -> str:
    return pbkdf2_sha256.hash(key)


def verify_key(key: str, key_hash: str) -> bool:
    return pbkdf2_sha256.verify(key, key_hash)


def generate_key() -> str:
    return f"hf_{secrets.token_urlsafe(32)}"


async def get_current_key(
    request: Request,
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    client_ip = _get_client_ip(request)
    await _check_lockout(client_ip)

    # Check admin key first (constant-time comparison)
    if secrets.compare_digest(api_key, settings.admin_api_key):
        await _clear_failure(client_ip)
        admin = ApiKey(
            name="admin",
            key_hash="",
            scopes=ALL_SCOPES,
            is_active=True,
        )
        return admin

    # Look up in DB by prefix
    key_prefix = api_key[:12] if len(api_key) >= 12 else api_key

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.is_active.is_(True),
            ApiKey.key_prefix == key_prefix,
        )
    )
    keys = result.scalars().all()

    if not keys:
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.is_active.is_(True),
                ApiKey.key_prefix.is_(None),
            )
        )
        keys = result.scalars().all()

    for db_key in keys:
        if verify_key(api_key, db_key.key_hash):
            await _clear_failure(client_ip)
            updates = {"last_used_at": datetime.now(timezone.utc)}
            if not db_key.key_prefix:
                updates["key_prefix"] = key_prefix
            await db.execute(
                update(ApiKey).where(ApiKey.id == db_key.id).values(**updates)
            )
            await db.commit()
            return db_key

    await _record_failure(client_ip)
    logger.warning("Failed auth attempt from %s", client_ip)
    raise HTTPException(status_code=401, detail="Invalid API key")


def require_scope(scope: str):
    async def checker(key: ApiKey = Depends(get_current_key)):
        if "admin" in key.scopes:
            return key
        if scope not in key.scopes:
            raise HTTPException(
                status_code=403, detail=f"Key lacks required scope: {scope}"
            )
        return key

    return checker
