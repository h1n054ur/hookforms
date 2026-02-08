from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_key, hash_key, require_scope
from app.database import get_db
from app.models.api_key import ApiKey
from app.response import paginated_response, single_response
from app.schemas.auth import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/keys", status_code=201, summary="Create an API key")
async def create_key(
    body: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("admin")),
):
    raw_key = generate_key()
    db_key = ApiKey(
        name=body.name,
        key_hash=hash_key(raw_key),
        key_prefix=raw_key[:12],
        scopes=body.scopes,
    )
    db.add(db_key)
    await db.commit()
    await db.refresh(db_key)

    resp = ApiKeyResponse.model_validate(db_key)
    result = ApiKeyCreated(**resp.model_dump(), raw_key=raw_key)
    return single_response(result)


@router.get("/keys", summary="List API keys")
async def list_keys(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("admin")),
):
    total = (await db.execute(select(func.count()).select_from(ApiKey))).scalar()
    result = await db.execute(
        select(ApiKey).order_by(ApiKey.created_at.desc()).limit(limit).offset(offset)
    )
    items = [ApiKeyResponse.model_validate(k) for k in result.scalars().all()]
    return paginated_response(items, total, limit, offset)


@router.delete("/keys/{key_id}", status_code=204, summary="Revoke an API key")
async def revoke_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("admin")),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    db_key = result.scalar_one_or_none()
    if not db_key:
        raise HTTPException(status_code=404, detail="API key not found")
    db_key.is_active = False
    await db.commit()
