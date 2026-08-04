from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_analytics_repository
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.common import envelope
from app.services import analytics_service

router = APIRouter(prefix="/geography", tags=["geography"])


@router.get("/state-performance")
def state_performance(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_state_performance(repo))
