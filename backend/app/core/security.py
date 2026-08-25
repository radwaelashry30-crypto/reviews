"""API key authentication -- disabled by default (REQUIRE_API_KEY=false),
same philosophy as ENABLE_BERT: the app keeps
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


async def require_marketplace_admin_key(x_api_key: str | None = Header(default=None)) -> str:
    """Write/administrative marketplace-data routes (upload, mapping, preview,
    confirm, rollback, session deletion, raw-row access) must never be
    reachable by an anonymous visitor of the published site -- see the
    Checkpoint A requirement this closes: 'no anonymous Replace of published
    data'. Unlike require_api_key, this check is NOT gated by
    REQUIRE_API_KEY -- it always enforces a key, even on a deployment that
    otherwise runs the rest of the API open. At least one real value in
    API_KEYS is therefore a hard prerequisite for enabling marketplace writes
    at all; see MODEL page / deployment docs.

    Returns settings.MARKETPLACE_ADMIN_ACTOR_ID, NOT the raw key: callers use
    this return value as the 'actor' persisted in created_by/actor columns
    (import sessions, dataset versions, the audit log). The raw admin API
    key must never reach the database, a log line, or a response body --
    the key is validated here (still via secrets.compare_digest, still
    rejecting every invalid/missing value exactly as before) and then
    discarded; only the static, non-secret actor label survives past this
    function.
    """
    if not settings.API_KEYS or not x_api_key or not any(secrets.compare_digest(x_api_key, k) for k in settings.API_KEYS):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key (required for marketplace data administration)",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return settings.MARKETPLACE_ADMIN_ACTOR_ID
