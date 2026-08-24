"""Orchestrates the full 2-task review-analysis pipeline:

    Task 1: sentiment (Positive/Negative)
              |
    Task 2: aspect-based sentiment (price / quality / delivery / service / packaging)

Task 2 always runs, for either sentiment.

Task 2 depends on a model that is never loaded at API startup -- see
ModelRegistry.get_absa_pipeline. On a RAM-constrained deployment it simply
reports "available": false with a reason, rather than crashing the process.
"""
from __future__ import annotations

from app.ml.absa import ABSA_ASPECTS, analyze_aspects_single
from app.services.model_registry import ModelRegistry
from app.services.sentiment_service import predict_sentiment


def run_full_pipeline(
    registry: ModelRegistry, text: str, model_name: str = "bert",
    source_language: str = "en", translate: bool = False,
    aspects: list[str] | None = None,
) -> dict:
    """Task 1 -> Task 2. Returns both results together."""
    sentiment = predict_sentiment(registry, text, model_name=model_name, source_language=source_language, translate=translate)
    analyzed_text = sentiment["cleaned_text"]

    absa_pipe = registry.get_absa_pipeline()
    if absa_pipe is not None:
        aspects_result = analyze_aspects_single(absa_pipe, analyzed_text, aspects=aspects or ABSA_ASPECTS)
    else:
        status = registry.statuses.get("absa")
        aspects_result = {"available": False, "reason": status.error if status else "not loaded"}

    return {
        "sentiment": sentiment,
        "aspects": aspects_result,
    }
