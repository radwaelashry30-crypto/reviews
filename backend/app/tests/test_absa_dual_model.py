"""Focused tests for the dual-model ABSA feature (CNN2D default + optional
lazy-loaded DeBERTa-v3). Mocks the DeBERTa loader everywhere -- these tests
must never download the real ~738MB checkpoint.

CNN2D's own scoring/gating logic is untouched by this feature; its coverage
lives in test_absa.py and is not duplicated here."""
import pydantic
import pytest

from app.ml.absa import ABSA_ASPECTS, analyze_aspects_single
from app.schemas.sentiment import FullPipelineRequest
from app.services.model_registry import ModelRegistry

DELIVERY_ONLY_REVIEW = "The delivery guy was super friendly and dropped it off right on time."


def _fake_hf_pipe_factory(label="Negative", score=0.91):
    """Mimics the shape of a real HF text-classification pipeline call:
    pipe(text, text_pair=aspect, truncation=True) -> [{"label", "score"}].
    Records the exact text_pair (aspect) each call received."""
    calls = []

    def fake_pipe(text, text_pair=None, truncation=True):
        calls.append(text_pair)
        return [{"label": label, "score": score}]

    return fake_pipe, calls


# -- 1/4: schema-level default and validation ---------------------------

def test_absa_model_defaults_to_cnn2d_when_omitted():
    req = FullPipelineRequest(text="Great product.")
    assert req.absa_model == "cnn2d"


def test_absa_model_accepts_explicit_cnn2d():
    req = FullPipelineRequest(text="Great product.", absa_model="cnn2d")
    assert req.absa_model == "cnn2d"


def test_absa_model_accepts_explicit_deberta():
    req = FullPipelineRequest(text="Great product.", absa_model="deberta")
    assert req.absa_model == "deberta"


def test_absa_model_invalid_value_rejected():
    with pytest.raises(pydantic.ValidationError):
        FullPipelineRequest(text="Great product.", absa_model="fake_review_model")


# -- 5/6/7: lazy loading, startup behavior, caching ----------------------

def test_deberta_not_loaded_during_registry_startup(monkeypatch, tmp_path):
    """load_all() must never touch the DeBERTa loader, even indirectly."""
    from app.core.config import settings

    calls = []
    monkeypatch.setattr("app.ml.absa.load_deberta_absa_pipeline", lambda device=-1: calls.append(device) or object())
    monkeypatch.setattr(settings, "BERT_MODEL_PATH", tmp_path / "no_bert")
    monkeypatch.setattr(settings, "CNN_CHECKPOINT_PATH", tmp_path / "no_cnn.pt")
    monkeypatch.setattr(settings, "CNN_TOKENIZER_PATH", tmp_path / "no_tok.pkl")
    monkeypatch.setattr(settings, "RFM_SCALER_PATH", tmp_path / "no_scaler.pkl")
    monkeypatch.setattr(settings, "RFM_MODEL_PATH", tmp_path / "no_kmeans.pkl")

    registry = ModelRegistry()
    registry.load_all()

    assert calls == []
    assert registry.absa_deberta_pipe is None
    assert "absa_deberta" not in registry.statuses


def test_deberta_lazy_loaded_only_when_explicitly_selected(monkeypatch):
    calls = []
    sentinel = object()
    monkeypatch.setattr("app.ml.absa.load_deberta_absa_pipeline", lambda device=-1: calls.append(device) or sentinel)

    registry = ModelRegistry()
    assert registry.absa_deberta_pipe is None
    assert calls == []

    pipe = registry.get_absa_pipeline(absa_method="deberta")

    assert pipe is sentinel
    assert calls == [-1]  # CPU device index, since no CUDA in this registry's default state
    assert registry.statuses["absa_deberta"].status == "available"


def test_repeated_deberta_requests_reuse_cached_pipeline(monkeypatch):
    calls = []
    monkeypatch.setattr("app.ml.absa.load_deberta_absa_pipeline", lambda device=-1: calls.append(1) or object())

    registry = ModelRegistry()
    pipe1 = registry.get_absa_pipeline(absa_method="deberta")
    pipe2 = registry.get_absa_pipeline(absa_method="deberta")
    pipe3 = registry.get_absa_pipeline(absa_method="deberta")

    assert len(calls) == 1, "the loader must only run once; every later call must reuse the cached pipeline"
    assert pipe1 is pipe2 is pipe3


def test_cnn2d_still_selected_by_default_path(monkeypatch):
    """absa_method='cnn2d' (or omitted) must never touch the DeBERTa loader."""
    deberta_calls = []
    monkeypatch.setattr("app.ml.absa.load_deberta_absa_pipeline", lambda device=-1: deberta_calls.append(1) or object())

    registry = ModelRegistry()
    # No CNN2D loaded -> None is the correct, non-crashing result for the default path.
    result = registry.get_absa_pipeline()
    assert result is None
    assert registry.statuses["absa"].status == "unavailable"
    assert deberta_calls == []


# -- 8: DeBERTa loading failure is controlled, never crashes -------------

def test_deberta_loading_failure_returns_none_with_reason(monkeypatch):
    def _boom(device=-1):
        raise OSError("simulated network failure downloading yangheng/deberta-v3-base-absa-v1.1")

    monkeypatch.setattr("app.ml.absa.load_deberta_absa_pipeline", _boom)

    registry = ModelRegistry()
    result = registry.get_absa_pipeline(absa_method="deberta")

    assert result is None
    status = registry.statuses["absa_deberta"]
    assert status.status == "loading_failed"
    assert "simulated network failure" in status.error


def test_full_pipeline_service_reports_unavailable_not_crash_on_deberta_failure(monkeypatch):
    from app.services.advanced_sentiment_service import run_full_pipeline

    monkeypatch.setattr("app.ml.absa.load_deberta_absa_pipeline", lambda device=-1: (_ for _ in ()).throw(RuntimeError("boom")))

    registry = ModelRegistry()
    # Force sentiment to a harmless fixed result so this test isolates ABSA behavior
    # without needing real BERT/CNN2D sentiment artifacts.
    monkeypatch.setattr(
        "app.services.advanced_sentiment_service.predict_sentiment",
        lambda registry, text, model_name="bert", source_language="en", translate=False: {
            "label": "Negative", "cleaned_text": text, "confidence": 0.9,
            "probability_positive": 0.1, "probability_negative": 0.9,
            "model_name": model_name, "source_language": source_language,
            "translated": False, "analysis_id": None,
        },
    )

    result = run_full_pipeline(registry, "The item arrived broken.", absa_method="deberta")

    assert result["aspects"]["available"] is False
    assert "reason" in result["aspects"]
    assert "fake" not in result["aspects"]["reason"].lower()


# -- 9/10: gating and input contract, method-agnostic --------------------

def test_not_mentioned_aspects_are_never_scored_with_deberta(monkeypatch):
    fake_pipe, calls = _fake_hf_pipe_factory()
    result = analyze_aspects_single(fake_pipe, DELIVERY_ONLY_REVIEW, aspects=ABSA_ASPECTS, absa_method="deberta")
    by_aspect = {r["aspect"]: r for r in result["aspects"]}

    assert "delivery" in calls
    for aspect in ["product quality", "price", "customer service", "packaging"]:
        assert aspect not in calls
        assert by_aspect[aspect]["sentiment"] == "Not mentioned"
        assert by_aspect[aspect]["confidence"] == 0.0


def test_deberta_receives_aspect_via_text_pair_per_verified_contract():
    """Verified against the checkpoint's own model card: classifier(sentence,
    text_pair=aspect). The mentioned aspect must be passed as text_pair, not
    concatenated into the text or dropped."""
    fake_pipe, calls = _fake_hf_pipe_factory()
    text = "Terrible customer service and the product broke after two days."

    analyze_aspects_single(fake_pipe, text, aspects=["customer service", "product quality"], absa_method="deberta")

    assert "customer service" in calls
    assert "product quality" in calls


# -- 11: label mapping passthrough is correct -----------------------------

def test_deberta_label_mapping_passthrough_matches_verified_config():
    """yangheng/deberta-v3-base-absa-v1.1's own config.json id2label is
    {0: Negative, 1: Neutral, 2: Positive} -- these already match this
    project's vocabulary, so the pipeline's raw pred["label"] must pass
    through unchanged, for every one of the three real labels."""
    for label in ("Negative", "Neutral", "Positive"):
        fake_pipe, _ = _fake_hf_pipe_factory(label=label, score=0.77)
        result = analyze_aspects_single(fake_pipe, DELIVERY_ONLY_REVIEW, aspects=["delivery"], absa_method="deberta")
        assert result["aspects"][0]["sentiment"] == label
        assert result["aspects"][0]["confidence"] == 0.77


def test_deberta_result_reports_deberta_specific_model_description():
    fake_pipe, _ = _fake_hf_pipe_factory()
    result = analyze_aspects_single(fake_pipe, DELIVERY_ONLY_REVIEW, aspects=["delivery"], absa_method="deberta")
    assert "deberta" in result["model"].lower()
    assert "more accurate" not in result["methodology_note"].lower()
    assert "fake" not in result["model"].lower()


def test_cnn2d_result_reports_cnn_specific_model_description():
    fake_pipe, _ = _fake_hf_pipe_factory()
    result = analyze_aspects_single(fake_pipe, DELIVERY_ONLY_REVIEW, aspects=["delivery"])  # absa_method omitted -> default
    assert "cnn2d" in result["model"].lower()
    assert "deberta" not in result["model"].lower()
