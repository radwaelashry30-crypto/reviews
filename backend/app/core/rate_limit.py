"""Per-IP rate limiting (slowapi/limits), in-memory -- single-process deployment,
no shared store needed. Kept in its own module so both main.py (setup) and
individual endpoint modules (decorators) can import the same `limiter`
instance without a circular import.
"""
from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Generous enough for normal dashboard/analytics polling; specific expensive
# endpoints (model inference, file upload) set tighter per-route limits below.
DEFAULT_LIMITS = ["120/minute"]

limiter = Limiter(key_func=get_remote_address, default_limits=DEFAULT_LIMITS)


def register_rate_limiter(app) -> None:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit_exceeded(request: Request, exc: RateLimitExceeded):
        request_id = str(uuid.uuid4())
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMITED",
                    "message": f"Too many requests. Limit: {exc.detail}.",
                    "details": {},
                },
                "meta": {"request_id": request_id},
            },
        )
