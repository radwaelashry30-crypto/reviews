from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_model_registry
from app.schemas.common import envelope
from app.schemas.sentiment import BatchPredictionRequest, SentimentPredictionRequest
from app.services import sentiment_service
from app.services.model_registry import ModelRegistry

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.post("/predict")
def predict(payload: SentimentPredictionRequest, registry: ModelRegistry = Depends(get_model_registry)):
    result = sentiment_service.predict_sentiment(
        registry, payload.text, model_name=payload.model_name,
        source_language=payload.source_language, translate=payload.translate,
    )
    return envelope(result, model_version=payload.model_name)


@router.post("/predict-batch")
def predict_batch(payload: BatchPredictionRequest, registry: ModelRegistry = Depends(get_model_registry)):
    items = [{"id": item.id, "text": item.text} for item in payload.items]
    results = sentiment_service.predict_sentiment_batch(registry, items, model_name=payload.model_name)
    return envelope({"results": results, "n_items": len(results)}, model_version=payload.model_name)
