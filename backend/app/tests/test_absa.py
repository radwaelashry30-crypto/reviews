"""Regression tests for the ABSA hallucination fix (see app/ml/absa.py module
docstring). Uses a fake pipeline callable so these run deterministically and
fast without needing the real (optional, download-gated) ABSA model."""
from app.ml.absa import ABSA_ASPECTS, _aspect_mentioned, analyze_aspects_single

DELIVERY_ONLY_REVIEW = "The delivery guy was super friendly and dropped it off right on time."


def _fake_pipe_factory():
    """Records which aspects the model was actually queried for, and always
    returns a confident Positive -- if the gate fails, every aspect below
    would incorrectly come back Positive with a high score."""
    calls = []

    def fake_pipe(text, text_pair=None, truncation=True):
        calls.append(text_pair)
        return [{"label": "Positive", "score": 0.99}]

    return fake_pipe, calls


def test_aspect_mentioned_true_when_keyword_present():
    assert _aspect_mentioned(DELIVERY_ONLY_REVIEW, "delivery")


def test_aspect_mentioned_false_when_keyword_absent():
    assert not _aspect_mentioned(DELIVERY_ONLY_REVIEW, "product quality")
    assert not _aspect_mentioned(DELIVERY_ONLY_REVIEW, "customer service")
    assert not _aspect_mentioned(DELIVERY_ONLY_REVIEW, "price")
    assert not _aspect_mentioned(DELIVERY_ONLY_REVIEW, "packaging")


def test_analyze_aspects_single_never_queries_model_for_unmentioned_aspects():
    """Confirmed bug this fixes: this exact review previously produced
    'product quality: Positive 75.1%' from the live model, despite quality
    never being mentioned. The keyword gate must skip the model call for
    any aspect with no matching keyword, not just downweight it."""
    fake_pipe, calls = _fake_pipe_factory()

    result = analyze_aspects_single(fake_pipe, DELIVERY_ONLY_REVIEW, aspects=ABSA_ASPECTS)
    by_aspect = {r["aspect"]: r for r in result["aspects"]}

    # The only genuinely-mentioned aspect: model is queried and its answer used.
    assert "delivery" in calls
    assert by_aspect["delivery"]["sentiment"] == "Positive"

    # Every other aspect: never queried, reported as not mentioned rather than guessed.
    for aspect in ["product quality", "price", "customer service", "packaging"]:
        assert aspect not in calls, f"model should never have been queried for unmentioned aspect {aspect!r}"
        assert by_aspect[aspect]["sentiment"] == "Not mentioned"
        assert by_aspect[aspect]["confidence"] == 0.0


def test_analyze_aspects_single_queries_model_when_multiple_aspects_present():
    text = "Terrible customer service and the product broke after two days, total waste of money."
    fake_pipe, calls = _fake_pipe_factory()

    result = analyze_aspects_single(fake_pipe, text, aspects=ABSA_ASPECTS)
    by_aspect = {r["aspect"]: r for r in result["aspects"]}

    for aspect in ["customer service", "product quality", "price"]:
        assert aspect in calls
        assert by_aspect[aspect]["sentiment"] == "Positive"  # fake pipe always says Positive; just confirms it was called

    assert "delivery" not in calls
    assert by_aspect["delivery"]["sentiment"] == "Not mentioned"
