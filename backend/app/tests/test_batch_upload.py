import io

import pytest


def _bert_available(client) -> bool:
    status = client.get("/api/v1/models/status").json()["data"]
    return status["artifacts"].get("bert", {}).get("status") == "available"


def _csv_with_dates() -> bytes:
    rows = [
        "review_comment_message_en,review_creation_date",
        "This product is excellent and arrived early,2026-01-05",
        "Terrible quality broke after one day,2026-01-06",
        "Great value amazing service,2026-01-12",
        "Awful experience would not recommend,2026-01-13",
    ]
    return ("\n".join(rows)).encode("utf-8")


def _csv_without_dates() -> bytes:
    rows = [
        "review_comment_message_en",
        "This product is excellent and arrived early",
        "Terrible quality broke after one day",
    ]
    return ("\n".join(rows)).encode("utf-8")


def test_upload_file_rejects_oversized_file(client):
    """Regression test for the unbounded-read DoS vector: a file over the 5MB
    cap must be rejected with 400 before it's ever handed to pandas, not
    silently buffered into memory in full."""
    oversized = b"review_comment_message_en\n" + (b'"padding padding padding",\n' * 250_000)
    assert len(oversized) > 5 * 1024 * 1024
    resp = client.post(
        "/api/v1/sentiment/upload-file",
        files={"file": ("reviews.csv", oversized, "text/csv")},
        data={"model_name": "cnn2d"},
    )
    assert resp.status_code == 400
    assert "5MB" in resp.json()["error"]["message"] or "limit" in resp.json()["error"]["message"].lower()


def test_upload_file_basic_includes_top_words_and_time_trend(client):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")

    files = {"file": ("reviews.csv", io.BytesIO(_csv_with_dates()), "text/csv")}
    resp = client.post("/api/v1/sentiment/upload-file", files=files, data={"model_name": "bert", "advanced": "false"})
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert "top_words" in data
    assert "top_positive_words" in data["top_words"]
    assert "top_negative_words" in data["top_words"]

    assert "time_trend" in data
    assert data["time_trend"]["available"] is True
    assert data["time_trend"]["date_column_used"].lower() == "review_creation_date"
    assert len(data["time_trend"]["points"]) >= 1

    # advanced=false means these keys are simply absent
    assert "fake_review_summary" not in data
    assert "aspect_summary" not in data


def test_upload_file_without_date_column_reports_time_trend_unavailable(client):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")

    files = {"file": ("reviews.csv", io.BytesIO(_csv_without_dates()), "text/csv")}
    resp = client.post("/api/v1/sentiment/upload-file", files=files, data={"model_name": "bert"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["time_trend"]["available"] is False


def test_upload_file_advanced_includes_fake_and_aspect_summaries(client):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")

    files = {"file": ("reviews.csv", io.BytesIO(_csv_with_dates()), "text/csv")}
    resp = client.post("/api/v1/sentiment/upload-file", files=files, data={"model_name": "bert", "advanced": "true"})
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert "advanced_sample_size" in data
    assert data["advanced_sample_size"] >= 1

    assert "fake_review_summary" in data
    assert "available" in data["fake_review_summary"]

    assert "aspect_summary" in data
    assert "available" in data["aspect_summary"]
    if data["aspect_summary"]["available"]:
        assert data["aspect_summary"]["per_aspect"]
        for row in data["aspect_summary"]["per_aspect"]:
            assert set(row) >= {"aspect", "n", "n_mentioned", "mentioned_pct", "positive_pct", "neutral_pct", "negative_pct"}
