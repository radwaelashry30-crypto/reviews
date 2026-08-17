"""Tests for the self-consistency check in app/ml/fake_review_detection.py.

Uses a fake pipeline callable so the reliable/unreliable branches are tested
deterministically and fast, without needing the real (optional,
download-gated) model. See fake_review_decision_basis_test.py for the live
evidence this check exists to surface, not hide."""
import pytest

from app.ml.fake_review_detection import generate_stability_probes, score_with_stability_check


def _label_pair(p: float):
    """Matches the real pipeline's top_k=None output shape: pipe(text)
    returns a batch-wrapped list, and score_single_review takes [0] of it."""
    return [[{"label": "LABEL_0", "score": 1 - p}, {"label": "LABEL_1", "score": p}]]


def _pipe_returning(probability_fake: float):
    """Fake pipeline: every call (base text or any probe) returns the same
    fixed fake-probability, regardless of input text."""
    def pipe(text, truncation=True):
        return _label_pair(probability_fake)
    return pipe


def _pipe_cycling(*probabilities: float):
    """Fake pipeline: returns each probability in sequence across successive
    calls (base call first, then each probe), to simulate an unstable model."""
    values = iter(probabilities)

    def pipe(text, truncation=True):
        return _label_pair(next(values))
    return pipe


def test_generate_stability_probes_returns_requested_count():
    probes = generate_stability_probes("The product broke after two days.", n=2)
    assert len(probes) == 2
    assert all(isinstance(p, str) and p for p in probes)


def test_generate_stability_probes_preserve_rough_meaning():
    """Probes should still resemble the original text (this is a reword
    check, not a random-text generator)."""
    text = "The delivery was late and the box was damaged."
    probes = generate_stability_probes(text, n=2)
    for probe in probes:
        assert len(probe) >= len(text) * 0.6


def test_score_with_stability_check_marks_reliable_when_consistent():
    pipe = _pipe_returning(0.95)  # every call, base and probes alike, agrees
    result = score_with_stability_check(pipe, "Great product, very happy with it.")
    assert result["available"] is True
    assert result["stability_checked"] is True
    assert result["reliable"] is True
    assert result["verdict_spread"] < 0.2


def test_score_with_stability_check_marks_unreliable_when_verdict_swings():
    # base=0.99 (confidently "fake"), first probe=0.01 (confidently "real") -- exactly
    # the kind of flip observed against the real model (see MODEL_COMPARISON_AUDIT.md).
    pipe = _pipe_cycling(0.99, 0.01, 0.99)
    result = score_with_stability_check(pipe, "The material feels flimsy and cheap.", n_variants=2)
    assert result["available"] is True
    assert result["reliable"] is False
    assert result["verdict_spread"] >= 0.2
    assert "do not trust" in result["reliability_note"].lower()


def test_score_with_stability_check_propagates_unavailable():
    def broken_pipe(text, truncation=True):
        raise RuntimeError("model not loaded")

    result = score_with_stability_check(broken_pipe, "Some review text.")
    assert result["available"] is False
