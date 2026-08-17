"""Optional, EXPERIMENTAL aspect-based sentiment analysis (sentiment-given-aspect).

Notebook §13 (cell 147) runs `yangheng/deberta-v3-base-absa-v1.1` via the
`text-classification` pipeline with `text_pair=<aspect>` over a fixed
candidate aspect list. Olist reviews have NO ground-truth aspect labels, so
this scores sentiment GIVEN a predefined aspect, not full automatic aspect
extraction. Does not download the model at import time.

CONFIRMED BUG (found via live testing, fixed here): `yangheng/deberta-v3-base-
absa-v1.1` is an Aspect-Term SENTIMENT model, not an aspect DETECTOR -- it was
trained on datasets (SemEval Laptop/Restaurant, MAMS) where the queried aspect
was always genuinely present in the sentence, so it has no "not mentioned"
class and will confidently hallucinate a sentiment for any aspect you force it
to score. Verified empirically: for the review "The delivery guy was super
friendly and dropped it off right on time." (only about delivery), the model
returned "product quality: Positive 75.1%" -- a class of product never
mentioned. For "This laptop is garbage, completely broke after two days."
(only about the product itself), it returned Negative for delivery/price/
customer service/packaging, none of which appear in the text (customer
service scored 98.8% confidence). The prior code queried all 5 fixed aspects
on every review regardless of content.

Fix: `_aspect_mentioned()` gates each aspect behind a lexical presence check
(ASPECT_KEYWORDS) before the model is ever called for it. If no keyword for
an aspect appears in the text, that aspect is reported as "Not mentioned"
without a model call, instead of a hallucinated Positive/Negative/Neutral.
This is a heuristic, not a perfect detector -- it can miss aspects discussed
without any of the listed keywords (a false negative just means that aspect
is skipped, which is no worse than the un-gated behavior for aspects never
queried) and can occasionally admit a keyword used in an unrelated sense (a
false positive just falls back to the original model-scored behavior). It
directly eliminates the confirmed failure mode above: neither "quality" nor
"customer service" appears in the delivery-only example, so that call is now
skipped entirely rather than guessed.
"""
from __future__ import annotations

import re

import pandas as pd

ABSA_MODEL = "yangheng/deberta-v3-base-absa-v1.1"
ABSA_ASPECTS = ["delivery", "product quality", "price", "customer service", "packaging"]
DEFAULT_SAMPLE_SIZE = 200

NOT_MENTIONED_LABEL = "Not mentioned"

# Deliberately simple/lexical (not stemmed or fuzzy) so the gate stays fast,
# dependency-free, and auditable. Word-boundary matched, case-insensitive.
ASPECT_KEYWORDS: dict[str, list[str]] = {
    "delivery": [
        "deliver", "delivery", "delivered", "delivering", "shipping", "shipped", "ship",
        "arrive", "arrived", "arriving", "courier", "package", "parcel", "postal", "post",
        "mail", "tracking", "late", "on time", "dispatch",
    ],
    "product quality": [
        "quality", "material", "materials", "durable", "durability", "broke", "broken",
        "defect", "defective", "sturdy", "flimsy", "cheaply made", "well made", "craftsmanship",
        "fabric", "build quality", "fell apart", "damaged", "faulty", "works well", "worked well",
    ],
    "price": [
        "price", "priced", "pricing", "cost", "costly", "expensive", "cheap", "cheaper",
        "affordable", "value for money", "worth", "money", "overpriced", "pricey", "discount",
        "cost-effective", "cheapest", "budget",
    ],
    "customer service": [
        "customer service", "support", "representative", "staff", "helpline", "response",
        "responded", "refund", "return policy", "complaint", "assistance", "help desk",
        "customer care", "agent", "call center",
    ],
    "packaging": [
        "packaging", "package box", "box", "boxed", "wrapped", "wrapping", "bubble wrap",
        "seal", "sealed", "container", "damaged box", "crushed box",
    ],
}


def _aspect_mentioned(text: str, aspect: str) -> bool:
    """Cheap lexical presence check -- see module docstring for why this
    gate exists. Falls back to True (query the model) for any aspect without
    a curated keyword list, preserving prior behavior for custom aspects."""
    keywords = ASPECT_KEYWORDS.get(aspect)
    if not keywords:
        return True
    lowered = text.lower()
    return any(re.search(r"\b" + re.escape(kw) + r"\b", lowered) for kw in keywords)


def is_absa_model_available() -> bool:
    try:
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def load_absa_pipeline(device: int = -1):
    """Loads the pipeline once. Callers (ModelRegistry) should cache and reuse it."""
    from transformers import pipeline

    return pipeline("text-classification", model=ABSA_MODEL, device=device)


def analyze_aspects_single(pipe, text: str, aspects: list[str] | None = None) -> dict:
    """Score one review across each aspect with an already-loaded pipeline.
    Used by the live inference pipeline (Task 3).

    Each aspect is gated behind `_aspect_mentioned()` first -- see module
    docstring. Aspects with no keyword match are reported as "Not mentioned"
    without ever calling the model, instead of a hallucinated verdict."""
    aspects = aspects or ABSA_ASPECTS
    records = []
    for aspect in aspects:
        if not _aspect_mentioned(text, aspect):
            records.append({"aspect": aspect, "sentiment": NOT_MENTIONED_LABEL, "confidence": 0.0})
            continue
        try:
            pred = pipe(text, text_pair=aspect, truncation=True)[0]
            records.append({"aspect": aspect, "sentiment": pred["label"], "confidence": round(float(pred["score"]), 4)})
        except Exception as e:
            records.append({"aspect": aspect, "sentiment": "UNKNOWN", "confidence": 0.0, "error": str(e)})
    return {
        "available": True,
        "model": ABSA_MODEL,
        "aspects": records,
        "methodology_note": (
            "Sentiment-given-aspect over a fixed candidate aspect list, not automatic aspect "
            "extraction. An aspect is only scored by the model if the review's text contains a "
            "related keyword; otherwise it's reported as \"Not mentioned\" rather than guessed."
        ),
    }


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
            if not _aspect_mentioned(text, aspect):
                results.append({
                    "review_id": review_id, "aspect": aspect,
                    "sentiment": NOT_MENTIONED_LABEL, "confidence": 0.0,
                })
                continue
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
