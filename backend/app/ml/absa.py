"""Optional, EXPERIMENTAL aspect-based sentiment analysis (sentiment-given-aspect).

Notebook §13 (cell 147) runs `yangheng/deberta-v3-base-absa-v1.1` via the
`text-classification` pipeline with `text_pair=<aspect>` over a fixed
candidate aspect list. Olist reviews have NO ground-truth aspect labels, so
this scores sentiment GIVEN a predefined aspect, not full automatic aspect
extraction. Does not download the model at import time.
"""
from __future__ import annotations

import pandas as pd

ABSA_MODEL = "yangheng/deberta-v3-base-absa-v1.1"
ABSA_ASPECTS = ["delivery", "product quality", "price", "customer service", "packaging"]
DEFAULT_SAMPLE_SIZE = 200


def is_absa_model_available() -> bool:
    try:
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def run_absa(
    reviews: pd.DataFrame,
    text_column: str = "review_comment_message_en",
    review_id_column: str = "review_id",
    aspects: list[str] | None = None,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: int = 42,
    device: int = -1,
) -> dict:
    """Score `sample_size` reviews x each aspect for sentiment-given-aspect.

    Returns a long-format record list: {review_id, aspect, sentiment, confidence}.
    """
    from transformers import pipeline

    aspects = aspects or ABSA_ASPECTS
    pool = reviews[reviews[text_column].fillna("").astype(str).str.strip() != ""]
    sample = pool.sample(min(sample_size, len(pool)), random_state=seed)

    try:
        pipe = pipeline("text-classification", model=ABSA_MODEL, device=device)
    except Exception as e:
        return {"available": False, "reason": f"Could not load {ABSA_MODEL}: {e}"}

    results = []
    for aspect in aspects:
        for review_id, text in zip(sample[review_id_column], sample[text_column]):
            try:
                pred = pipe(text, text_pair=aspect, truncation=True)[0]
            except Exception:
                pred = {"label": "UNKNOWN", "score": 0.0}
            results.append({
                "review_id": review_id, "aspect": aspect,
                "sentiment": pred["label"], "confidence": float(pred["score"]),
            })

    return {
        "available": True,
        "model": ABSA_MODEL,
        "aspects": aspects,
        "sample_size": len(sample),
        "n_predictions": len(results),
        "records": results,
        "methodology_note": (
            "This is sentiment-given-aspect over a fixed candidate aspect list, "
            "not automatic aspect extraction. Olist reviews have no manually "
            "annotated aspect labels."
        ),
    }
