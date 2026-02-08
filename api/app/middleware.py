"""Rate limiting + security headers middleware."""

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.redis import redis as redis_client

logger = logging.getLogger(__name__)


def _get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter using Redis sorted sets.

    - 100 requests/min per IP
    - Fails closed (503) when Redis is unavailable
    """

    WINDOW_SECONDS = 60
    LIMIT = 100

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health check
        if request.url.path == "/health":
            response = await call_next(request)
            for header, value in _SECURITY_HEADERS.items():
                response.headers[header] = value
            return response

        client_ip = _get_client_ip(request)
        key = f"ratelimit:{client_ip}"
        now = time.time()
        window_start = now - self.WINDOW_SECONDS

        try:
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {f"{now}": now})
            pipe.expire(key, self.WINDOW_SECONDS + 1)
            results = await pipe.execute()
            current_count = results[1]
        except Exception:
            logger.error("Redis unavailable for rate limiting — denying request")
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": 503,
                        "message": "Service temporarily unavailable. Please try again.",
                    }
                },
                headers=_SECURITY_HEADERS,
            )

        remaining = max(0, self.LIMIT - current_count - 1)
        reset_at = int(now + self.WINDOW_SECONDS)

        if current_count >= self.LIMIT:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {"code": 429, "message": "Too many requests. Please retry later."}
                },
                headers={
                    **_SECURITY_HEADERS,
                    "X-RateLimit-Limit": str(self.LIMIT),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.LIMIT)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)

        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies larger than 2 MB."""

    MAX_BODY_SIZE = 2 * 1024 * 1024

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": 413,
                        "message": f"Request body too large. Max size is {self.MAX_BODY_SIZE // (1024 * 1024)} MB.",
                    }
                },
            )

        return await call_next(request)
