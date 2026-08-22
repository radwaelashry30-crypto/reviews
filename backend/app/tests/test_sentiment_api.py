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


def test_pipeline_returns_sentiment_even_when_task2_model_unavailable(client):
    """Task 2 (fake-review) depends on a model not loaded by default
    (ENABLE_FAKE_REVIEW_MODULE=false in tests). Task 3 (ABSA) runs on CNN2D,
    which IS loaded by default, so it's expected to be available here -- see
    app/ml/absa.py and ModelRegistry.get_absa_pipeline(). The pipeline must
    still return Task 1's sentiment result and a graceful 'unavailable'
    payload for Task 2, never a 500."""
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    resp = client.post("/api/v1/sentiment/pipeline", json={"text": "The item arrived broken.", "model_name": "bert"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sentiment"]["label"] in ("Positive", "Negative")
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


def test_explain_requires_nonempty_text(client):
    resp = client.post("/api/v1/sentiment/explain", json={"text": "   "})
    assert resp.status_code == 422


def test_explain_degrades_gracefully_without_shap_or_bert(client):
    """SHAP needs the `shap` package + a loaded BERT model but never
    downloads anything at request time -- if either is missing it must
    report 'available: false', never a 500."""
    resp = client.post("/api/v1/sentiment/explain", json={"text": "The product works great."})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "available" in data
    if data["available"]:
        assert isinstance(data.get("top_tokens_toward_positive"), list)
    else:
        assert data.get("reason")


def test_upload_file_rejects_unsupported_extension(client):
    resp = client.post(
        "/api/v1/sentiment/upload-file",
        files={"file": ("reviews.txt", b"some text", "text/plain")},
        data={"model_name": "cnn2d"},
    )
    assert resp.status_code == 400


def test_upload_file_rejects_empty_file(client):
    resp = client.post(
        "/api/v1/sentiment/upload-file",
        files={"file": ("reviews.csv", b"", "text/csv")},
        data={"model_name": "cnn2d"},
    )
    assert resp.status_code == 400


def test_upload_file_classifies_csv_rows(client):
    if not _cnn_available(client):
        pytest.skip("CNN2D artifact not available in this environment.")
    csv_content = (
        b"review_comment_message_en,other_col\n"
        b'"Fast delivery and great quality, very happy!",x\n'
        b'"Terrible product, broke after one day.",y\n'
        b",z\n"  # empty text row, should be skipped
    )
    resp = client.post(
        "/api/v1/sentiment/upload-file",
        files={"file": ("reviews.csv", csv_content, "text/csv")},
        data={"model_name": "cnn2d"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["text_column_used"] == "review_comment_message_en"
    assert data["total_rows_in_file"] == 3
    assert data["n_classified"] == 2
    assert data["n_skipped_empty_or_error"] == 1
    assert data["n_positive"] + data["n_negative"] == 2
    assert len(data["results"]) == 2
    assert data["upload_id"]
    assert data["retention_days"] == 7


def test_upload_file_result_retrievable_by_id(client):
    """Results are saved for 7 days -- GET should return the exact same
    classification without re-uploading."""
    if not _cnn_available(client):
        pytest.skip("CNN2D artifact not available in this environment.")
    csv_content = b"text\n\"Excellent, would buy again!\"\n"
    upload_resp = client.post(
        "/api/v1/sentiment/upload-file",
        files={"file": ("reviews.csv", csv_content, "text/csv")},
        data={"model_name": "cnn2d"},
    )
    upload_id = upload_resp.json()["data"]["upload_id"]

    get_resp = client.get(f"/api/v1/sentiment/upload-file/{upload_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["upload_id"] == upload_id
    assert data["n_classified"] == 1
    assert "expires_at" in data


def test_upload_file_unknown_id_returns_404(client):
    # Well-formed (32-char hex, matching uuid4().hex) but never issued -- see
    # test_upload_id_validation.py for malformed-id rejection (422).
    resp = client.get("/api/v1/sentiment/upload-file/" + "0" * 32)
    assert resp.status_code == 404


def test_upload_file_rejects_file_with_no_text_column(client):
    if not _cnn_available(client):
        pytest.skip("CNN2D artifact not available in this environment.")
    csv_content = b"a,b\n1,2\n3,4\n"
    resp = client.post(
        "/api/v1/sentiment/upload-file",
        files={"file": ("data.csv", csv_content, "text/csv")},
        data={"model_name": "cnn2d"},
    )
    assert resp.status_code == 400


def test_predict_translation_disabled_by_default(client):
    resp = client.post(
        "/api/v1/sentiment/predict",
        json={"text": "O produto chegou rapido", "model_name": "bert", "source_language": "pt", "translate": True},
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"
