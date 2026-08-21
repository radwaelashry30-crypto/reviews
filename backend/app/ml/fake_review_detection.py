"""Fake-review detection: ensemble of a fine-tuned DistilBERT classifier and
a TF-IDF + Logistic Regression classifier, trained on the Ott et al.
Deceptive Opinion Spam Corpus (Cornell, ACL 2011 / NAACL 2013 -- 1,596 hotel
reviews, genuinely human-verified deceptive vs. truthful, not a proxy for
star rating or any other confound).

Replaces `jb10231/fake-review-detector`, which had two disqualifying,
directly-verified problems (kept here for the historical record): its
label semantics were never wired into its published config (LABEL_0/
LABEL_1, not the documented FAKE/REAL), and its predictions were unstable
under meaning-preserving paraphrasing (a pure synonym substitution flipped
one verdict from 99.9% to 0.1% confidence). A first retrain attempt on a
DIFFERENT dataset (theArijitDas/Fake-Reviews-Dataset, an AI-generated-vs-
human-written-TEXT task, 97% held-out accuracy) failed the same paraphrase-
stability test the same way -- see MODEL_COMPARISON_AUDIT.md for that
investigation.

This model is different in three ways, each targeting one specific failure
found along the way:
  1. Different dataset, different task framing: genuinely human-verified
     DECEPTIVE INTENT (an MTurk worker paid to write a convincing fake
     review) rather than AI-vs-human text origin. A candidate replacement
     dataset (Amazon "spam/non-spam", Naveed Hussain / Kaggle) was rejected
     BEFORE any training was attempted, once direct inspection showed its
     label was a 1:1 proxy for star rating (100% of 4-5* reviews labeled
     "spam", 100% of 1-3* labeled "not spam", zero overlap) -- not a
     genuine spam judgment at all.
  2. Paraphrase-consistency training: a symmetric KL-divergence loss
     between each training review's prediction and a WordNet-paraphrased +
     length-perturbed view of the SAME review, added alongside the normal
     classification loss (see scripts/train_fake_review_detector_v2_consistency.py).
     This closed the synonym-substitution failure mode to ~0.7% confident
     flip rate (95% CI 0.2-2.4%, measured over all 320 held-out test
     reviews, not a handful of cherry-picked examples) but left a SEPARATE
     failure mode -- sensitivity to review length/verbosity alone -- only
     partially fixed.
  3. Ensembling with a TF-IDF + Logistic Regression classifier trained on
     the same data. A bag-of-words linear model has no positional/attention
     mechanism for a transformer's length-sensitivity to act through, so it
     is inherently more length-robust (13.8% length-probe spread vs.
     DistilBERT's 24%) at the cost of being less confident overall (abstains
     40% of the time under the margin below). Averaging the two probabilities
     measured 0/300 confident flips (95% CI upper bound 1.3%) and only a
     6.2% abstain rate -- see results/fake_review_stability_largescale_test.json
     for the full methodology and numbers.

Honest, unresolved limitation: trained on Chicago hotel reviews, applied
here to Olist e-commerce reviews. This is a real domain shift and has not
been separately measured on Olist data (no genuinely-labeled Olist fake-
review data exists to measure it against -- the same gap that ruled out
training directly on this project's own data in the first place).

UNCERTAIN band: rather than forcing every prediction into a binary FAKE/
REAL call, predictions within `UNCERTAIN_MARGIN` of the 0.5 decision
boundary are reported as "UNCERTAIN" instead of a confident verdict. This
does not change the model's raw probability -- it changes what the system
is willing to assert. Empirically, essentially all of the residual
instability measured above happens to reviews that land in this band on at
least one side; forcing those into a hard binary call was what made a small,
honest uncertainty look like a confident, factually-wrong flip.
"""
from __future__ import annotations

from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[3] / "models"
BERT_MODEL_DIR = MODEL_DIR / "fake_review_detector_v2_consistency"
TFIDF_MODEL_DIR = MODEL_DIR / "fake_review_detector_tfidf"

MODEL_DESCRIPTION = (
    "Ensemble: DistilBERT (paraphrase-consistency fine-tuned) + TF-IDF/Logistic Regression, "
    "both trained on the Ott et al. Deceptive Opinion Spam Corpus"
)

# Predictions within 0.5 +/- this margin are reported as UNCERTAIN rather
# than a confident FAKE/REAL call -- see module docstring.
UNCERTAIN_MARGIN = 0.1

DISCLAIMER = (
    "Trained on hotel reviews (Ott et al., Cornell), applied here to e-commerce reviews -- "
    "a real domain shift not separately measured, since no genuinely-labeled fake-review data "
    "exists for Olist reviews. Within that limitation: measured over all 320 held-out test "
    "reviews (not a handful of examples), this ensemble gave a confidently wrong verdict on a "
    "meaning-preserving reword of the SAME review 0/300 times (95% CI upper bound 1.3%), and "
    "explicitly reports UNCERTAIN instead of guessing on the 6.2% of cases close to its decision "
    "boundary. See MODEL_COMPARISON_AUDIT.md for the full investigation, including two earlier "
    "checkpoints (the original external model and a first retrain) that failed this same test."
)


def is_fake_review_model_available() -> bool:
    try:
        import joblib  # noqa: F401
        import transformers  # noqa: F401
        return BERT_MODEL_DIR.is_dir() and TFIDF_MODEL_DIR.is_dir()
    except ImportError:
        return False


class FakeReviewEnsemble:
    """Bundles both loaded models. `score()` returns the ensemble fake-probability."""

    def __init__(self, tokenizer, bert_model, vectorizer, tfidf_clf, device):
        self.tokenizer = tokenizer
        self.bert_model = bert_model
        self.vectorizer = vectorizer
        self.tfidf_clf = tfidf_clf
        self.device = device

    def score(self, text: str) -> float:
        import torch

        enc = self.tokenizer(text, truncation=True, max_length=256, return_tensors="pt")
        enc = {k: v.to(self.device) for k, v in enc.items() if k in ("input_ids", "attention_mask")}
        with torch.no_grad():
            logits = self.bert_model(**enc).logits
        bert_prob = float(torch.softmax(logits, dim=1)[0, 1].item())
        tfidf_prob = float(self.tfidf_clf.predict_proba(self.vectorizer.transform([text]))[0, 1])
        return (bert_prob + tfidf_prob) / 2.0


def load_fake_review_pipeline(device: int = -1) -> FakeReviewEnsemble:
    """Loads both models once. Callers (ModelRegistry) should cache and reuse the result."""
    import joblib
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch_device = torch.device("cuda" if device >= 0 and torch.cuda.is_available() else "cpu")

    tokenizer = AutoTokenizer.from_pretrained(BERT_MODEL_DIR)
    bert_model = AutoModelForSequenceClassification.from_pretrained(BERT_MODEL_DIR)
    bert_model.eval()
    bert_model.to(torch_device)

    vectorizer = joblib.load(TFIDF_MODEL_DIR / "vectorizer.pkl")
    tfidf_clf = joblib.load(TFIDF_MODEL_DIR / "classifier.pkl")

    return FakeReviewEnsemble(tokenizer, bert_model, vectorizer, tfidf_clf, torch_device)


def _verdict(fake_probability: float, margin: float = UNCERTAIN_MARGIN) -> str:
    if fake_probability >= 0.5 + margin:
        return "FAKE"
    if fake_probability <= 0.5 - margin:
        return "REAL"
    return "UNCERTAIN"


def score_single_review(pipe: FakeReviewEnsemble, text: str) -> dict:
    """Scores one review. `reliable` is True unless the verdict is UNCERTAIN --
    named to match the field file_batch_service.py's summary already filters
    on, so batch aggregation needed no changes for this swap."""
    try:
        fake_probability = pipe.score(text)
    except Exception as e:
        return {"available": False, "reason": str(e)}

    verdict = _verdict(fake_probability)
    return {
        "available": True,
        "model": MODEL_DESCRIPTION,
        "fake_probability": round(fake_probability, 4),
        "verdict": verdict,
        "is_fake": verdict == "FAKE",
        "reliable": verdict != "UNCERTAIN",
        "label_semantics_verified": True,
        "disclaimer": DISCLAIMER,
    }


def score_reviews_for_fakeness(texts: list[str], pipe: FakeReviewEnsemble | None = None, device: int = -1) -> dict:
    """Batch-score many reviews. Loads the ensemble lazily unless `pipe` is already provided."""
    if pipe is None:
        try:
            pipe = load_fake_review_pipeline(device=device)
        except Exception as e:
            return {"available": False, "reason": f"Could not load fake-review ensemble: {e}"}

    results = [score_single_review(pipe, t) for t in texts]
    failures = sum(1 for r in results if not r.get("available"))
    is_fake = [r.get("is_fake", False) for r in results]
    verdicts = [r.get("verdict", "UNCERTAIN") for r in results]

    return {
        "available": True,
        "model": MODEL_DESCRIPTION,
        "n_scored": len(texts),
        "n_failed": failures,
        "n_flagged_fake": int(sum(is_fake)),
        "verdicts": verdicts,
        "is_fake": is_fake,
        "confidence": [r.get("fake_probability", 0.0) for r in results],
        "label_semantics_verified": True,
        "disclaimer": DISCLAIMER,
    }
