from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.db.base import check_db_connection, db_configured
from app.schemas.common import envelope

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
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
