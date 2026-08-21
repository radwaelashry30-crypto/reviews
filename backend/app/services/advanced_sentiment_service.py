"""Orchestrates the full 3-task review-analysis pipeline:

    Task 1: sentiment (Positive/Negative)
              |
       Negative -> Task 2: fake vs. real check (see fake_review_detection.py)
              |                        |
              +------------------------+
                        |
              Task 3: aspect-based sentiment (price / quality / delivery / service / packaging)

Task 2 only runs when Task 1 says Negative (matches the product's intended
flow: fake-review screening matters most for negative reviews, which can
unfairly damage a seller's rating). Task 3 always runs, for either sentiment.

Both Task 2 and Task 3 depend on models that are never loaded at API startup
-- see ModelRegistry.get_fake_review_pipeline / get_absa_pipeline. On a
RAM-constrained deployment they simply report "available": false with a
reason, rather than crashing the process.
"""
from __future__ import annotations

from app.ml.absa import ABSA_ASPECTS, analyze_aspects_single
from app.ml.fake_review_detection import score_single_review
from app.services.model_registry import ModelRegistry
from app.services.sentiment_service import predict_sentiment


def run_full_pipeline(
    registry: ModelRegistry, text: str, model_name: str = "bert",
    source_language: str = "en", translate: bool = False,
    aspects: list[str] | None = None,
) -> dict:
    """Task 1 -> (if Negative) Task 2 -> Task 3. Returns all three results together."""
    sentiment = predict_sentiment(registry, text, model_name=model_name, source_language=source_language, translate=translate)
    analyzed_text = sentiment["cleaned_text"]

    fake_check = None
    if sentiment["label"] == "Negative":
        pipe = registry.get_fake_review_pipeline()
        if pipe is not None:
            fake_check = score_single_review(pipe, analyzed_text)
        else:
            status = registry.statuses.get("fake_review")
            fake_check = {"available": False, "reason": status.error if status else "not loaded"}

    absa_pipe = registry.get_absa_pipeline()
    if absa_pipe is not None:
        aspects_result = analyze_aspects_single(absa_pipe, analyzed_text, aspects=aspects or ABSA_ASPECTS)
    else:
        status = registry.statuses.get("absa")
        aspects_result = {"available": False, "reason": status.error if status else "not loaded"}

    return {
        "sentiment": sentiment,
        "fake_check": fake_check,
        "aspects": aspects_result,
    }
