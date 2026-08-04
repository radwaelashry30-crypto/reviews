from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_analytics_repository
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.common import envelope
from app.services import analytics_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/categories")
def categories(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_category_performance(repo))


@router.get("/category-performance")
def category_performance(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_category_performance(repo))
