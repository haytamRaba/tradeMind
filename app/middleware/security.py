"""Security middleware: rate limiting, API key auth, input sanitization."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.middleware.logging import get_correlation_id

settings = get_settings()

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# In-memory rate limiter (use Redis in production)
class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()
        window_start = now - window_seconds

        # Clean old entries
        self.requests[key] = [ts for ts in self.requests[key] if ts > window_start]

        # Check limit
        if len(self.requests[key]) >= limit:
            return False

        # Add current request
        self.requests[key].append(now)
        return True


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    def __init__(self, app: FastAPI, default_limit: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/health/ready", "/health/live"]:
            return await call_next(request)

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("X-API-Key", "")
        key = f"{client_ip}:{api_key}"

        # Different limits for different endpoints
        if request.url.path.startswith("/api/v1/market-data"):
            limit = settings.rate_limit_market_data if hasattr(settings, "rate_limit_market_data") else 30
        elif request.url.path.startswith("/api/v1/agents"):
            limit = settings.rate_limit_agents if hasattr(settings, "rate_limit_agents") else 10
        else:
            limit = self.default_limit

        if not rate_limiter.is_allowed(key, limit, self.window_seconds):
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Window": str(self.window_seconds),
                    "X-Correlation-ID": get_correlation_id() or "",
                },
            )

        response = await call_next(request)
        return response


async def verify_api_key(
    api_key: str = Depends(api_key_header),
) -> str:
    """Verify API key for protected endpoints."""
    if not settings.api_key:
        # No API key configured, allow all
        return ""

    if not api_key or api_key != settings.api_key.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


# Input sanitization patterns
SUSPICIOUS_PATTERNS = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"union\s+select", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
    re.compile(r"insert\s+into", re.IGNORECASE),
    re.compile(r"delete\s+from", re.IGNORECASE),
    re.compile(r"update\s+\w+\s+set", re.IGNORECASE),
    re.compile(r"--\s*$"),
    re.compile(r";\s*$"),
]


class SanitizationMiddleware(BaseHTTPMiddleware):
    """Sanitize request inputs to prevent injection attacks."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check query parameters
        for key, value in request.query_params.items():
            if isinstance(value, str) and self._is_suspicious(value):
                return Response(
                    content='{"detail": "Suspicious input detected"}',
                    status_code=status.HTTP_400_BAD_REQUEST,
                    media_type="application/json",
                )

        # Note: Body sanitization would require reading the body,
        # which can only be done once. Consider using Pydantic validators instead.

        return await call_next(request)

    def _is_suspicious(self, value: str) -> bool:
        """Check if input contains suspicious patterns."""
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(value):
                return True
        return False


def add_security_middleware(app: FastAPI) -> None:
    """Add all security middleware to the app."""
    app.add_middleware(SanitizationMiddleware)
    app.add_middleware(RateLimitMiddleware)