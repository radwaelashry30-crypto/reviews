"""API key authentication -- disabled by default (REQUIRE_API_KEY=false),
same philosophy as ENABLE_BERT/ALLOW_EXTERNAL_MODEL_DOWNLOADS: the app keeps
working exactly as before unless an operator explicitly opts in by setting
REQUIRE_API_KEY=true and at least one key in API_KEYS.

Applied at the router level (see api/v1/router.py), not endpoint-by-endpoint,
so a newly added route is covered automatically instead of being an easy
thing to forget.
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str | None:
    if not settings.REQUIRE_API_KEY:
        return None  # local dev / current default deployment: open
    if not x_api_key or not any(secrets.compare_digest(x_api_key, k) for k in settings.API_KEYS):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
