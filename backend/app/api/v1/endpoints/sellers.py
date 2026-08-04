from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_analytics_repository
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.common import envelope
from app.services import analytics_service

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.get("/summary")
def seller_summary(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_seller_summary(repo))


@router.get("/performance")
def seller_performance(n: int = 20, repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_seller_performance(repo, n=n))
