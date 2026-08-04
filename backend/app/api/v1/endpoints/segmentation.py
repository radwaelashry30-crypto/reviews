from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_analytics_repository, get_model_registry
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.common import envelope
from app.schemas.segmentation import RfmPredictionRequest
from app.services import segmentation_service
from app.services.model_registry import ModelRegistry

router = APIRouter(prefix="/segmentation", tags=["segmentation"])


@router.get("/rfm-summary")
def rfm_summary(repo: AnalyticsRepository = Depends(get_analytics_repository)):
    return envelope(segmentation_service.get_rfm_summary(repo))


@router.post("/predict")
def predict(payload: RfmPredictionRequest, registry: ModelRegistry = Depends(get_model_registry)):
    result = segmentation_service.predict_customer_segment(registry, payload.recency, payload.frequency, payload.monetary)
    return envelope(result)
