import pytest

from app.core.exceptions import ModelUnavailableError
from app.services.model_registry import ModelRegistry


def test_registry_reports_unavailable_before_load():
    registry = ModelRegistry()
    with pytest.raises(ModelUnavailableError):
        registry.require_bert()
    with pytest.raises(ModelUnavailableError):
        registry.require_cnn()
    with pytest.raises(ModelUnavailableError):
        registry.require_rfm()


def test_registry_load_all_never_crashes_on_missing_artifacts(monkeypatch, tmp_path):
    from app.core.config import settings

    monkeypatch.setattr(settings, "BERT_MODEL_PATH", tmp_path / "no_bert")
    monkeypatch.setattr(settings, "CNN_CHECKPOINT_PATH", tmp_path / "no_cnn.pt")
    monkeypatch.setattr(settings, "CNN_TOKENIZER_PATH", tmp_path / "no_tok.pkl")
    monkeypatch.setattr(settings, "RFM_SCALER_PATH", tmp_path / "no_scaler.pkl")
    monkeypatch.setattr(settings, "RFM_MODEL_PATH", tmp_path / "no_kmeans.pkl")

    registry = ModelRegistry()
    registry.load_all()  # must not raise even though nothing exists

    assert registry.statuses["bert"].status == "unavailable"
    assert registry.statuses["cnn2d"].status == "unavailable"
    assert registry.statuses["rfm"].status == "unavailable"


def test_registry_status_report_structure():
    registry = ModelRegistry()
    report = registry.status_report()
    assert "device" in report
    assert "artifacts" in report


def test_registry_loads_real_artifacts_when_present(project_root):
    bert_dir = project_root / "models" / "bert_review_sentiment"
    if not bert_dir.is_dir():
        pytest.skip("No real BERT artifact present in this environment.")
    registry = ModelRegistry()
    registry.load_all()
    assert registry.statuses["bert"].status == "available"
    model, tokenizer = registry.require_bert()
    assert model is not None and tokenizer is not None
    # loading a second time must reuse the same in-memory object, not reload from disk
    model2, _ = registry.require_bert()
    assert model is model2
