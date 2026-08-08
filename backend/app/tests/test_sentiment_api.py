import pytest

from app.core.config import settings


def _bert_available(client) -> bool:
    status = client.get("/api/v1/models/status").json()["data"]
    return status["artifacts"].get("bert", {}).get("status") == "available"


def _cnn_available(client) -> bool:
    status = client.get("/api/v1/models/status").json()["data"]
    return status["artifacts"].get("cnn2d", {}).get("status") == "available"


def test_predict_requires_nonempty_text(client):
    resp = client.post("/api/v1/sentiment/predict", json={"text": "   ", "model_name": "bert"})
    assert resp.status_code == 422


def test_predict_invalid_model_name_rejected(client):
    resp = client.post("/api/v1/sentiment/predict", json={"text": "fine", "model_name": "not_a_model"})
    assert resp.status_code == 422


def test_predict_bert_success(client):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    resp = client.post("/api/v1/sentiment/predict", json={"text": "The product arrived early and works perfectly.", "model_name": "bert"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["label"] in ("Positive", "Negative")
    assert data["class_id"] in (0, 1)
    assert 0.0 <= data["probability_positive"] <= 1.0
    assert 0.0 <= data["probability_negative"] <= 1.0
    assert abs(data["probability_positive"] + data["probability_negative"] - 1.0) < 1e-3


def test_predict_cnn2d_success(client):
    if not _cnn_available(client):
        pytest.skip("CNN2D artifact not available in this environment.")
    resp = client.post("/api/v1/sentiment/predict", json={"text": "Terrible product, broke immediately.", "model_name": "cnn2d"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["label"] == "Negative"


def test_predict_deterministic_repeat(client):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    payload = {"text": "Great value for the price.", "model_name": "bert"}
    first = client.post("/api/v1/sentiment/predict", json=payload).json()["data"]
    second = client.post("/api/v1/sentiment/predict", json=payload).json()["data"]
    assert first["probability_positive"] == second["probability_positive"]


def test_predict_batch_preserves_ids(client):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    payload = {
        "items": [{"id": "review-1", "text": "Excellent product."}, {"id": "review-2", "text": "The item arrived broken."}],
        "model_name": "bert",
    }
    resp = client.post("/api/v1/sentiment/predict-batch", json=payload)
    assert resp.status_code == 200
    results = resp.json()["data"]["results"]
    assert [r["id"] for r in results] == ["review-1", "review-2"]


def test_predict_batch_rejects_empty(client):
    resp = client.post("/api/v1/sentiment/predict-batch", json={"items": [], "model_name": "bert"})
    assert resp.status_code == 422


def test_predict_batch_rejects_over_max_size(client):
    items = [{"id": str(i), "text": "ok"} for i in range(settings.MAX_BATCH_SIZE + 5)]
    resp = client.post("/api/v1/sentiment/predict-batch", json={"items": items, "model_name": "bert"})
    assert resp.status_code == 422


def test_pipeline_requires_nonempty_text(client):
    resp = client.post("/api/v1/sentiment/pipeline", json={"text": "  ", "model_name": "bert"})
    assert resp.status_code == 422


def test_pipeline_returns_sentiment_even_when_task2_task3_models_unavailable(client):
    """Task 2/3 depend on large external models not loaded by default
    (ALLOW_EXTERNAL_MODEL_DOWNLOADS=false in tests). The pipeline must still
    return Task 1's sentiment result and a graceful 'unavailable' payload for
    the other two, never a 500."""
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    resp = client.post("/api/v1/sentiment/pipeline", json={"text": "The item arrived broken.", "model_name": "bert"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sentiment"]["label"] in ("Positive", "Negative")
    assert data["aspects"]["available"] is False
    if data["sentiment"]["label"] == "Negative":
        assert data["fake_check"]["available"] is False
    else:
        assert data["fake_check"] is None


def test_pipeline_skips_fake_check_for_positive_sentiment(client):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    resp = client.post("/api/v1/sentiment/pipeline", json={"text": "Excellent product, arrived early.", "model_name": "bert"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    if data["sentiment"]["label"] == "Positive":
        assert data["fake_check"] is None


def test_predict_translation_disabled_by_default(client):
    resp = client.post(
        "/api/v1/sentiment/predict",
        json={"text": "O produto chegou rapido", "model_name": "bert", "source_language": "pt", "translate": True},
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"
