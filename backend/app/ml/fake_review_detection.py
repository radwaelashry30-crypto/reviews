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

import re

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
    "also unverified. Do not treat this output as a validated fraud signal. "
    "A retrained replacement (real, verified dataset, held-out accuracy 97%) was "
    "tested against the same instability check and failed it the same way, so this "
    "looks structural rather than a fixable bug in one checkpoint -- see "
    "scripts/paraphrase_stability_test.py and scripts/fake_review_decision_basis_test.py. "
    "Each verdict below is now automatically re-checked against a reworded version of "
    "the same review; see 'reliable'/'reliability_note' for whether THIS verdict held up."
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


# --------------------------------------------------------------------------- #
# Self-consistency check
# --------------------------------------------------------------------------- #
# Retraining on a real, verified dataset (scripts/train_fake_review_detector.py)
# did NOT fix the instability -- the retrained checkpoint failed the same
# paraphrase-stability test the same way (see scripts/paraphrase_stability_test.py
# results), and a follow-up diagnostic (scripts/fake_review_decision_basis_test.py)
# found no interpretable textual property (length, sentiment, specificity,
# register, punctuation, personal detail) that predicts the verdict either --
# three of four near-identical length variants of ONE sentence scored ~0% fake
# probability while a fourth spiked to 98.5%. This looks like a structural
# property of fine-tuned AI-text classifiers on this kind of task, not a fixable
# bug in one checkpoint.
#
# Since the model can't be made stable, this stops trying to hide that fact
# behind a static disclaimer and instead measures it per-review: score the
# review AND a couple of meaning-preserving rewordings of it, and if the
# verdict swings between them, say so explicitly rather than silently
# returning whichever one run happened to answer.

def _wordnet_variant(text: str, max_swaps: int = 3) -> str | None:
    """Meaning-preserving variant via WordNet synonym substitution on up to
    `max_swaps` content words. Deterministic (always picks the first distinct
    lemma found) so repeated calls on the same text are reproducible. Returns
    None if WordNet's corpus data isn't available locally."""
    try:
        from nltk.corpus import wordnet as wn
    except (ImportError, LookupError):
        return None

    words = text.split()
    new_words = []
    swapped = 0
    for word in words:
        core = re.sub(r"[^a-zA-Z]", "", word)
        replacement = None
        if swapped < max_swaps and len(core) > 3:
            try:
                synsets = wn.synsets(core.lower())
            except LookupError:
                return None
            for syn in synsets:
                for lemma in syn.lemmas():
                    name = lemma.name()
                    if "_" not in name and name.lower() != core.lower():
                        replacement = name
                        break
                if replacement:
                    break
        if replacement:
            new_words.append(word.replace(core, replacement, 1))
            swapped += 1
        else:
            new_words.append(word)
    return " ".join(new_words) if swapped else None


def _structural_variant(text: str) -> str:
    """Fallback probe when WordNet data isn't available: appends a short,
    meaning-neutral clause. Only used to test verdict stability, never shown
    to the user as "the" analyzed text -- see module docstring for why even
    this kind of trivial, meaning-preserving change is a valid stability
    probe for this specific model (length alone was measured to flip its
    verdict with no content change at all)."""
    return text.rstrip(". ") + ", overall."


def generate_stability_probes(text: str, n: int = 2) -> list[str]:
    """Returns up to `n` meaning-preserving variants of `text` to probe
    verdict stability against. Prefers WordNet synonym substitution; falls
    back to a structural probe if WordNet data isn't available, so this
    always produces at least one probe."""
    variants: list[str] = []
    wn_variant = _wordnet_variant(text)
    if wn_variant and wn_variant != text:
        variants.append(wn_variant)
    while len(variants) < n:
        source = variants[-1] if variants else text
        variants.append(_structural_variant(source))
    return variants[:n]


def score_with_stability_check(pipe, text: str, n_variants: int = 2, instability_threshold: float = 0.2) -> dict:
    """Scores `text`, then probes whether that verdict holds up under a
    couple of meaning-preserving rewordings of the SAME review. Returns the
    same shape as `score_single_review` plus:
      - reliable: bool -- False if fake_probability swung by more than
        `instability_threshold` across the probes (default 0.2 = 20 points).
      - verdict_spread: the actual max-min swing observed.
      - reliability_note: a plain-language explanation of what that means.

    This does not fix the underlying model -- nothing at the config/prompting
    level can (see module docstring and MODEL_COMPARISON_AUDIT.md). It turns
    a hidden failure mode into an explicit, per-review signal: a caller can
    now tell "verdict FAKE, and stable under rewording" apart from "verdict
    FAKE, but flips to REAL if you reword it slightly" instead of only ever
    seeing the first one.
    """
    base = score_single_review(pipe, text)
    if not base.get("available"):
        return base

    probes = generate_stability_probes(text, n=n_variants)
    probe_probs = []
    for probe_text in probes:
        result = score_single_review(pipe, probe_text)
        if result.get("available"):
            probe_probs.append(result["fake_probability"])

    all_probs = [base["fake_probability"], *probe_probs]
    spread = round(max(all_probs) - min(all_probs), 4) if len(all_probs) > 1 else 0.0
    reliable = spread < instability_threshold

    return {
        **base,
        "stability_checked": True,
        "n_probes": len(probe_probs),
        "verdict_spread": spread,
        "reliable": reliable,
        "reliability_note": (
            "Verdict was stable across meaning-preserving rewordings of this review."
            if reliable else
            f"Verdict changed by {spread:.0%} under a meaning-preserving reword of this SAME "
            "review -- do not trust this specific fake/real label."
        ),
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
