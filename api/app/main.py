from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.middleware import RateLimitMiddleware, RequestSizeLimitMiddleware
from app.redis import redis
from app.routers import auth, webhooks

API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    await redis.aclose()


app = FastAPI(
    title="HookForms",
    description="Receive webhook form submissions and forward them as email notifications.",
    version=API_VERSION,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# CORS
_cors_origins = (
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.cors_origins
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)


# --- Exception Handlers ---


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        clean = {k: v for k, v in err.items() if k != "ctx"}
        if "msg" in clean:
            clean["msg"] = str(clean["msg"])
        errors.append(clean)
    return JSONResponse(
        status_code=422,
        content={"error": {"code": 422, "message": "Validation error", "details": errors}},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": 500, "message": "Internal server error"}},
    )


# --- Routes ---

api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(auth.router)
api_v1.include_router(webhooks.router)
app.include_router(api_v1)

# Public webhook receiver (unversioned)
app.include_router(webhooks.public_router)


@app.get("/", summary="API root")
async def root():
    return {"name": settings.app_name, "status": "ok", "version": API_VERSION}


@app.get("/health", summary="Health check")
async def health_ping():
    status = "healthy"
    checks = {}

    try:
        from app.database import async_session

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "unavailable"
        status = "degraded"

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
        status = "degraded"

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": API_VERSION,
        "checks": checks,
    }
