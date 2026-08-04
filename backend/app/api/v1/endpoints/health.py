from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import envelope

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return envelope({
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    })
