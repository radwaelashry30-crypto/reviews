from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.exceptions import ResourceNotFoundError
from app.dependencies import get_analytics_repository
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.common import envelope
from app.services import analytics_service, segmentation_service

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/summary")
def customer_summary(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_customer_summary(repo))


@router.get("/top-cities")
def top_cities(n: int = 10, repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(analytics_service.get_top_cities(repo, n=n))


@router.get("/segments")
def segments(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(segmentation_service.get_rfm_summary(repo))


@router.get("/segments/{segment_name}")
def segment_detail(segment_name: str, repo: AnalyticsRepository = Depends(get_analytics_repository)):
    payload = segmentation_service.get_rfm_summary(repo)
    for row in payload.get("segment_summary", []):
        if row.get("Segment", "").lower() == segment_name.lower():
            return envelope(row)
    raise ResourceNotFoundError(f"Segment '{segment_name}' not found.", details={"available": [r.get("Segment") for r in payload.get("segment_summary", [])]})
