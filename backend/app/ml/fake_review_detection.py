"""Optional, EXPERIMENTAL fake-review scoring using an external pretrained model.

Notebook §12 (cell 145) runs `jb10231/fake-review-detector` (DistilBERT, fine-
tuned on 40K product reviews, binary FAKE/REAL) over the 11,407 negative
(1-2 star) reviews and reports 0 flagged as fake.

**Verified label bug in the original notebook**: the model card documents
labels "FAKE" (AI-generated/fake review) and "REAL" (genuine human review),
but the checkpoint's actual `config.json` was never given that `id2label`
mapping -- `AutoConfig.from_pretrained(...).id2label` returns the generic
placeholder `{0: "LABEL_0", 1: "LABEL_1"}`, verified directly. The notebook's
check `label.upper() == "FAKE"` therefore NEVER matches anything the model
can output -- the reported "0/11,407 flagged as fake" is not a genuine
finding about the dataset, it is an artifact of comparing against a string
the model never produces. Verified empirically on 30 real negative Olist
reviews: the model outputs LABEL_1 for ~6.7% of them (2/30), not 0%.

Because the checkpoint itself doesn't expose which index is "fake", this
module ASSUMES index 1 ("LABEL_1") is the fake/flagged class -- consistent
with (a) common binary-classifier convention, (b) fake reviews being the
rarer class in reality, and (c) LABEL_1 being the minority output in the
empirical spot-check above. This assumption is NOT verified against the
model's own config and is surfaced explicitly in every response via
`label_semantics_verified: false`.

**Second, more severe confirmed issue: predictions are not stable under
meaning-preserving paraphrasing.** Tested directly against the live model:
"The material feels flimsy and the color is different from the photos." ->
LABEL_1 at 99.9% confidence, but the same sentence reworded with synonyms
only -- "The fabric feels cheap and the color doesn't match the pictures."
-- flips to LABEL_1 at 0.1% confidence. Text length alone was also tested and
ruled out as the driver (a fixed sentence scored progressively closer to 0%
as filler clauses were appended, with no change in meaning). No content-level
pattern (genericness, topic, sentiment polarity, length) reproduced across
repeated tests, meaning the model is not keying on anything a human would
recognize as evidence of authenticity -- it is reacting to incidental lexical
choices from its own training corpus. Full investigation and evidence:
MODEL_COMPARISON_AUDIT.md.

This module is kept separate from sentiment classification, never downloads
the model at import time, and never presents its output as a validated
fraud signal.
"""
from __future__ import annotations

FAKE_REVIEW_MODEL = "jb10231/fake-review-detector"
DEFAULT_BATCH_SIZE = 32

# ASSUMED, not verified against the model's own config -- see module docstring.
ASSUMED_FAKE_LABEL = "LABEL_1"

DISCLAIMER = (
    "Exploratory only -- not a reliable signal. Rewording a review with pure "
    "synonyms (identical meaning) has been observed to flip this verdict "
    "entirely (99.9% -> 0.1% confidence in direct testing), so a different "
    "phrasing of the exact same review can produce the opposite verdict. "
    "This checkpoint's config.json also does not define what its "
    "output labels ('LABEL_0'/'LABEL_1') mean -- the model card's documented "
    "'FAKE'/'REAL' names were never wired into the published config. This "
    "module ASSUMES LABEL_1 = fake (common convention + empirically the "
    "minority class), but that mapping is not verified. Domain shift "
    "(translated Olist reviews vs. the model's original training data) is "
    "also unverified. Do not treat this output as a validated fraud signal."
)


def is_fake_review_model_available() -> bool:
    try:
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def load_fake_review_pipeline(device: int = -1):
    """Loads the pipeline once. Callers (ModelRegistry) should cache and reuse it."""
    from transformers import pipeline

    return pipeline("text-classification", model=FAKE_REVIEW_MODEL, device=device, top_k=None)


def _extract_fake_score(raw_result) -> tuple[str, float, float]:
    """raw_result is either a single {label,score} dict or (with top_k=None) a
    list of {label,score} for every class. Returns (top_label, top_score, fake_probability)."""
    if isinstance(raw_result, list):
        by_label = {r["label"]: float(r["score"]) for r in raw_result}
        top = max(raw_result, key=lambda r: r["score"])
        fake_prob = by_label.get(ASSUMED_FAKE_LABEL, 0.0)
        return top["label"], float(top["score"]), fake_prob
    label = raw_result["label"]
    score = float(raw_result["score"])
    fake_prob = score if label == ASSUMED_FAKE_LABEL else 1.0 - score
    return label, score, fake_prob


def score_single_review(pipe, text: str) -> dict:
    """Score one review with an already-loaded pipeline. Used by the live inference pipeline."""
    try:
        raw = pipe(text, truncation=True)[0]
        label, score, fake_prob = _extract_fake_score(raw if isinstance(raw, list) else [raw])
    except Exception as e:
        return {"available": False, "reason": str(e)}
    return {
        "available": True,
        "model": FAKE_REVIEW_MODEL,
        "raw_label": label,
        "raw_confidence": round(score, 4),
        "assumed_fake_label": ASSUMED_FAKE_LABEL,
        "is_fake": label == ASSUMED_FAKE_LABEL,
        "fake_probability": round(fake_prob, 4),
        "label_semantics_verified": False,
        "disclaimer": DISCLAIMER,
    }


def score_reviews_for_fakeness(texts: list[str], batch_size: int = DEFAULT_BATCH_SIZE, device: int = -1, pipe=None) -> dict:
    """Batch-score many reviews. Loads the model lazily unless `pipe` is already provided."""
    if pipe is None:
        try:
            pipe = load_fake_review_pipeline(device=device)
        except Exception as e:
            return {"available": False, "reason": f"Could not load {FAKE_REVIEW_MODEL}: {e}"}

    labels: list[str] = []
    scores: list[float] = []
    failures = 0
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        try:
            results = pipe(batch, truncation=True)
            for r in results:
                label, score, _ = _extract_fake_score(r if isinstance(r, list) else [r])
                labels.append(label)
                scores.append(score)
        except Exception:
            failures += len(batch)
            labels.extend(["UNKNOWN"] * len(batch))
            scores.extend([0.0] * len(batch))

    is_fake = [lbl == ASSUMED_FAKE_LABEL for lbl in labels]
    return {
        "available": True,
        "model": FAKE_REVIEW_MODEL,
        "n_scored": len(texts),
        "n_failed": failures,
        "n_flagged_fake": int(sum(is_fake)),
        "assumed_fake_label": ASSUMED_FAKE_LABEL,
        "label_semantics_verified": False,
        "labels": labels,
        "confidence": scores,
        "is_fake": is_fake,
        "disclaimer": DISCLAIMER,
    }
