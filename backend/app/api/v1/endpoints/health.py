from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import settings
from app.db.base import check_db_connection, db_configured
from app.schemas.common import envelope

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Deliberately lightweight -- never touches the marketplace dataset
    state (see GET /ready for that). Answers immediately regardless of
    whether a marketplace dataset version is loading, missing, or degraded,
    so a hosting platform's health check never fails/restart-loops on
    dataset state. See Checkpoint B correction #6."""
    db_status: dict = {"configured": db_configured()}
    if db_configured():
        ok, error = check_db_connection()
        db_status["connected"] = ok
        if not ok:
            db_status["error"] = error

    return envelope({
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    })


@router.get("/ready")
def ready(request: Request):
    """Reports the marketplace dataset's real readiness state -- separate
    from /health so a slow/degraded dataset load never affects the
    platform-level health check above. States: healthy (process up,
    independent of dataset), analytics_loading (not currently observable
    synchronously -- startup either finishes or fails fast, see
    MarketplaceAnalyticsCache), ready, degraded, database_unavailable."""
    cache = getattr(request.app.state, "marketplace_cache", None)
    report = cache.readiness_report() if cache is not None else {"readiness": "ready", "source": "historical_packaged", "active_version_id": None, "error": None}
    return envelope({"process": "healthy", **report})
