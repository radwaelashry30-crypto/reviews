from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_model_registry
from app.schemas.common import envelope
from app.schemas.sentiment import BatchPredictionRequest, ExplainRequest, FullPipelineRequest, SentimentPredictionRequest
from app.services import advanced_sentiment_service, sentiment_service
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


@router.post("/pipeline")
def full_pipeline(payload: FullPipelineRequest, registry: ModelRegistry = Depends(get_model_registry)):
    """Task 1 (sentiment) -> Task 2 (fake-vs-real, only if Negative) -> Task 3 (aspects, always).

    Task 2/3 depend on large external models (256MB / 706MB) not loaded at
    startup. On a RAM-constrained deployment they report
    `"available": false` inside their own result object rather than failing
    the whole request -- Task 1's sentiment result is always returned.
    """
    result = advanced_sentiment_service.run_full_pipeline(
        registry, payload.text, model_name=payload.model_name,
        source_language=payload.source_language, translate=payload.translate,
        aspects=payload.aspects,
    )
    return envelope(result, model_version=payload.model_name)


@router.post("/explain")
def explain(payload: ExplainRequest, registry: ModelRegistry = Depends(get_model_registry)):
    """SHAP token-level explanation for the fine-tuned BERT model (BERT only --
    CNN2D's embeddings aren't set up for SHAP's text masker). Explains the
    exact text the caller submits; not restricted to the stored test split
    (that restriction applies only to the audit/reproduction script)."""
    from app.ml.explainability import explain_single_review

    if registry.bert_model is None:
        return envelope({"available": False, "reason": "BERT model not available on this deployment"})

    explainer = registry.get_shap_explainer()
    if explainer is None:
        status = registry.statuses.get("shap")
        return envelope({"available": False, "reason": status.error if status else "not available"})

    result = explain_single_review(explainer, registry.bert_model, payload.text)
    return envelope(result, model_version="bert")
