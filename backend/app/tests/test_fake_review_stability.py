"""Tests for app/ml/fake_review_detection.py's verdict logic (REAL / UNCERTAIN
/ FAKE) and batch aggregation. Uses a fake ensemble object (returning a fixed
score()) so these are deterministic and fast, without needing the real
(257MB DistilBERT + TF-IDF) models. See MODEL_COMPARISON_AUDIT.md and
results/fake_review_stability_largescale_test.json for the live evidence
behind the UNCERTAIN-margin design (all measured on the real models)."""
from app.ml.fake_review_detection import FakeReviewEnsemble, UNCERTAIN_MARGIN, score_reviews_for_fakeness, score_single_review


class _FakeEnsemble:
    """Returns a fixed fake-probability regardless of input text."""

    description = "fake ensemble (test double)"
    disclaimer = "test double, not a real model"

    def __init__(self, probability: float):
        self.probability = probability

    def score(self, text: str) -> float:
        return self.probability


class _BrokenEnsemble:
    description = "fake ensemble (test double)"
    disclaimer = "test double, not a real model"

    def score(self, text: str) -> float:
        raise RuntimeError("model not loaded")


def test_score_single_review_confident_fake():
    pipe = _FakeEnsemble(0.5 + UNCERTAIN_MARGIN + 0.05)
    result = score_single_review(pipe, "Great product, very happy with it.")
    assert result["available"] is True
    assert result["verdict"] == "FAKE"
    assert result["is_fake"] is True
    assert result["reliable"] is True


def test_score_single_review_confident_real():
    pipe = _FakeEnsemble(0.5 - UNCERTAIN_MARGIN - 0.05)
    result = score_single_review(pipe, "The material feels flimsy and cheap.")
    assert result["available"] is True
    assert result["verdict"] == "REAL"
    assert result["is_fake"] is False
    assert result["reliable"] is True


def test_score_single_review_uncertain_band_is_not_confident():
    """Right at 0.5 -- squarely inside the UNCERTAIN margin -- must not be
    reported as a confident FAKE or REAL call."""
    pipe = _FakeEnsemble(0.5)
    result = score_single_review(pipe, "It's an okay product I guess.")
    assert result["available"] is True
    assert result["verdict"] == "UNCERTAIN"
    assert result["is_fake"] is False
    assert result["reliable"] is False


def test_score_single_review_boundary_is_confident_not_uncertain():
    """Exactly at the edge of the margin (0.5 + margin) should count as
    confident, not uncertain -- the band is (0.5-margin, 0.5+margin) exclusive
    of its own edges being folded into UNCERTAIN."""
    pipe = _FakeEnsemble(0.5 + UNCERTAIN_MARGIN)
    result = score_single_review(pipe, "Some review text.")
    assert result["verdict"] == "FAKE"


def test_score_single_review_propagates_unavailable():
    result = score_single_review(_BrokenEnsemble(), "Some review text.")
    assert result["available"] is False


def test_score_reviews_for_fakeness_aggregates_verdicts():
    pipe = _FakeEnsemble(0.5 + UNCERTAIN_MARGIN + 0.1)
    result = score_reviews_for_fakeness(["a", "b", "c"], pipe=pipe)
    assert result["available"] is True
    assert result["n_scored"] == 3
    assert result["n_flagged_fake"] == 3
    assert result["verdicts"] == ["FAKE", "FAKE", "FAKE"]


def test_ensemble_reports_tfidf_only_disclaimer_when_bert_absent():
    """FAKE_REVIEW_TFIDF_ONLY (app/core/config.py) constructs a
    FakeReviewEnsemble with bert_model=None -- the model/disclaimer text
    must honestly reflect which mode actually scored the review, since the
    two modes have measurably different abstain rates."""
    class _FakeVectorizer:
        def transform(self, texts):
            return texts

    class _FakeClassifier:
        def predict_proba(self, X):
            import numpy as np
            return np.array([[0.3, 0.7]])

    tfidf_only = FakeReviewEnsemble(None, None, _FakeVectorizer(), _FakeClassifier(), None)
    assert "TF-IDF" in tfidf_only.description
    assert "DistilBERT" not in tfidf_only.description
    assert "TF-IDF-only mode" in tfidf_only.disclaimer
    assert tfidf_only.score("some review text") == 0.7

    full_ensemble = FakeReviewEnsemble(object(), object(), _FakeVectorizer(), _FakeClassifier(), "cpu")
    assert "DistilBERT" in full_ensemble.description
    assert "TF-IDF-only mode" not in full_ensemble.disclaimer


def test_score_reviews_for_fakeness_mixed_verdicts():
    class _CyclingEnsemble:
        description = "fake ensemble (test double)"
        disclaimer = "test double, not a real model"

        def __init__(self, probs):
            self._probs = iter(probs)

        def score(self, text: str) -> float:
            return next(self._probs)

    pipe = _CyclingEnsemble([0.9, 0.1, 0.5])
    result = score_reviews_for_fakeness(["a", "b", "c"], pipe=pipe)
    assert result["verdicts"] == ["FAKE", "REAL", "UNCERTAIN"]
    assert result["n_flagged_fake"] == 1
