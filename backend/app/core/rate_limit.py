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

from app.core.config import settings

# Generous enough for normal dashboard/analytics polling; specific expensive
# endpoints (model inference, file upload) set tighter per-route limits below.
DEFAULT_LIMITS = ["120/minute"]


def client_identity(request: Request) -> str:
    """Behind a reverse proxy (Render, Vercel, any load balancer),
    get_remote_address() returns the PROXY's own address for every request --
    every real visitor shares one rate-limit bucket, which is both a false
    denial-of-service against legitimate traffic and no real limit on any
    single attacker. X-Forwarded-For is attacker-controlled at its FRONT
    (a client can prepend fake hops), but each trusted proxy in the chain
    appends the address it actually saw, so the entry TRUSTED_PROXY_HOPS
    positions from the end is the one only the deployment's own
    infrastructure could have written."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff and settings.TRUSTED_PROXY_HOPS > 0:
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        if len(hops) >= settings.TRUSTED_PROXY_HOPS:
            return f"ip:{hops[-settings.TRUSTED_PROXY_HOPS]}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=client_identity, default_limits=DEFAULT_LIMITS)


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
