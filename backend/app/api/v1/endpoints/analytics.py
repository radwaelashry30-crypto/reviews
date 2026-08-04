from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_analytics_repository
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.common import envelope
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
def summary(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_business_summary(repo))


@router.get("/orders/monthly")
def monthly_orders(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_monthly_orders(repo))


@router.get("/revenue/monthly")
def monthly_revenue(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_monthly_revenue(repo))


@router.get("/reviews/distribution")
def review_distribution(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_review_distribution(repo))


@router.get("/delivery/summary")
def delivery_summary(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_delivery_summary(repo))


@router.get("/payments/distribution")
def payment_distribution(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_payment_distribution(repo))
