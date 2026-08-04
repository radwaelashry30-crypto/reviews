"""Optional, EXPERIMENTAL fake-review scoring using an external pretrained model.

Notebook §12 (cell 145) runs `jb10231/fake-review-detector` (DistilBERT, fine-
tuned on 40K product reviews, binary FAKE/REAL) over the 11,407 negative
(1-2 star) reviews and reports 0 flagged as fake. That result is NOT evidence
that all negative reviews are genuine — plausible explanations include: the
model's training domain (generic product reviews, not Brazilian e-commerce
logistics complaints), the label threshold/calibration, and translated
(PT->EN via MarianMT) text differing systematically from the model's native
English training distribution. This module is kept separate from sentiment
classification and does not download the model at import time.
"""
from __future__ import annotations

FAKE_REVIEW_MODEL = "jb10231/fake-review-detector"
DEFAULT_BATCH_SIZE = 32


def is_fake_review_model_available() -> bool:
    try:
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def score_reviews_for_fakeness(texts: list[str], batch_size: int = DEFAULT_BATCH_SIZE, device: int = -1) -> dict:
    """Score each text as FAKE/REAL. Loads the external model lazily (only when called).

    Returns a payload including a domain-shift disclaimer, never presented as
    a validated fraud signal.
    """
    from transformers import pipeline

    try:
        pipe = pipeline("text-classification", model=FAKE_REVIEW_MODEL, device=device)
    except Exception as e:
        return {"available": False, "reason": f"Could not load {FAKE_REVIEW_MODEL}: {e}"}

    labels: list[str] = []
    scores: list[float] = []
    failures = 0
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        try:
            results = pipe(batch, truncation=True)
            labels.extend(r["label"] for r in results)
            scores.extend(float(r["score"]) for r in results)
        except Exception:
            failures += len(batch)
            labels.extend(["UNKNOWN"] * len(batch))
            scores.extend([0.0] * len(batch))

    is_fake = [str(lbl).upper() == "FAKE" for lbl in labels]
    return {
        "available": True,
        "model": FAKE_REVIEW_MODEL,
        "n_scored": len(texts),
        "n_failed": failures,
        "n_flagged_fake": int(sum(is_fake)),
        "labels": labels,
        "confidence": scores,
        "is_fake": is_fake,
        "disclaimer": (
            "Exploratory only. A 0% flagged-fake rate is not proof all reviews "
            "are genuine — it may reflect domain shift between this model's "
            "training data and translated Olist reviews, label-threshold "
            "calibration, or the specific negative-review subset scored. "
            "Do not treat this output as a validated fraud signal."
        ),
    }
