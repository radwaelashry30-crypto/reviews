"""Tests for the optional database persistence layer (app/db/, repositories,
and the /analyses + /feedback endpoints). Runs against a real, temporary
SQLite database per test session -- not mocked -- so schema/constraint/
cascade behavior is genuinely exercised, not assumed. The same models and
migration also target Postgres in production (see migrations/env.py); SQLite
here is a fast, dependency-free stand-in with the same SQLAlchemy-level
behavior for everything this suite checks.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
import app.db.base as db_base
from app.db.base import Base
from app.db.models import BatchUploadJob, PredictionFeedback, SentimentAnalysis, SentimentAnalysisAspect


@pytest.fixture(scope="module")
def db_available():
    """Points settings.DATABASE_URL at a fresh temp SQLite file for the
    duration of this module's tests, creates all tables, and resets the
    lazy engine/session singletons in app.db.base so they pick up the new
    URL. Restores everything afterward so other test modules (which run
    with no DB configured, by design) aren't affected."""
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "test.db"
    test_url = f"sqlite:///{db_path}"

    original_url = settings.DATABASE_URL
    original_engine, original_session_factory = db_base._engine, db_base._SessionLocal

    settings.DATABASE_URL = test_url
    db_base._engine = None
    db_base._SessionLocal = None

    engine = create_engine(test_url)
    Base.metadata.create_all(engine)

    yield test_url

    settings.DATABASE_URL = original_url
    db_base._engine = original_engine
    db_base._SessionLocal = original_session_factory


@pytest.fixture()
def session(db_available):
    factory = sessionmaker(bind=create_engine(db_available))
    s = factory()
    yield s
    s.close()


# --------------------------------------------------------------------------- #
# Connection / config
# --------------------------------------------------------------------------- #

def test_db_configured_reports_true_when_url_set(db_available):
    from app.db.base import db_configured
    assert db_configured() is True


def test_check_db_connection_succeeds(db_available):
    from app.db.base import check_db_connection
    ok, error = check_db_connection()
    assert ok is True
    assert error is None


# --------------------------------------------------------------------------- #
# sentiment_repository
# --------------------------------------------------------------------------- #

_SAMPLE_PREDICTION = {
    "label": "Positive", "class_id": 1, "probability_positive": 0.98, "probability_negative": 0.02,
    "confidence": 0.98, "model_name": "bert", "source_language": "en", "translated": False,
    "cleaned_text": "great product",
}


def test_save_and_get_analysis_round_trips(session):
    from app.repositories import sentiment_repository

    row = sentiment_repository.save_analysis(session, text="great product", prediction=_SAMPLE_PREDICTION)
    assert row.id is not None
    assert len(row.id) == 32  # uuid4().hex

    fetched = sentiment_repository.get_analysis(session, row.id)
    assert fetched is not None
    assert fetched.label == "Positive"
    assert fetched.confidence == 0.98


def test_save_analysis_with_aspects(session):
    from app.repositories import sentiment_repository

    aspects = [
        {"aspect": "delivery", "sentiment": "Positive", "confidence": 0.9},
        {"aspect": "price", "sentiment": "Not mentioned", "confidence": 0.0},
    ]
    row = sentiment_repository.save_analysis(session, text="fast delivery", prediction=_SAMPLE_PREDICTION, aspects=aspects)
    assert len(row.aspects) == 2
    assert {a.aspect for a in row.aspects} == {"delivery", "price"}


def test_get_analysis_returns_none_for_unknown_id(session):
    from app.repositories import sentiment_repository
    assert sentiment_repository.get_analysis(session, "does-not-exist") is None


def test_list_analyses_pagination_and_filtering(session):
    from app.repositories import sentiment_repository

    for i in range(5):
        pred = dict(_SAMPLE_PREDICTION, label="Negative" if i % 2 == 0 else "Positive")
        sentiment_repository.save_analysis(session, text=f"review {i}", prediction=pred)

    rows, total = sentiment_repository.list_analyses(session, limit=2, offset=0)
    assert len(rows) == 2
    assert total >= 5

    neg_rows, neg_total = sentiment_repository.list_analyses(session, limit=100, offset=0, label="Negative")
    assert neg_total >= 3
    assert all(r.label == "Negative" for r in neg_rows)


def test_cascade_delete_removes_aspects(session):
    from app.repositories import sentiment_repository

    row = sentiment_repository.save_analysis(
        session, text="x", prediction=_SAMPLE_PREDICTION,
        aspects=[{"aspect": "delivery", "sentiment": "Positive", "confidence": 0.9}],
    )
    aspect_id = row.aspects[0].id
    session.delete(row)
    session.commit()

    assert session.get(SentimentAnalysisAspect, aspect_id) is None


def test_save_feedback_round_trips(session):
    from app.repositories import sentiment_repository

    row = sentiment_repository.save_analysis(session, text="x", prediction=_SAMPLE_PREDICTION)
    feedback = sentiment_repository.save_feedback(session, analysis_id=row.id, is_correct=False, comment="wrong label")
    assert feedback is not None
    assert feedback.is_correct is False
    assert feedback.comment == "wrong label"


def test_save_feedback_returns_none_for_unknown_analysis(session):
    from app.repositories import sentiment_repository
    assert sentiment_repository.save_feedback(session, analysis_id="does-not-exist", is_correct=True) is None


# --------------------------------------------------------------------------- #
# batch_repository
# --------------------------------------------------------------------------- #

def test_batch_job_save_and_get_round_trips(session):
    from app.repositories import batch_repository

    result = {
        "filename": "reviews.csv", "model_name": "bert", "text_column_used": "text",
        "rows_processed": 3, "n_positive": 2, "n_negative": 1, "results": [{"row": 1, "text": "ok", "label": "Positive"}],
    }
    job_id = batch_repository.save_batch_job(session, result)
    assert len(job_id) == 32

    fetched = batch_repository.get_batch_job(session, job_id)
    assert fetched is not None
    assert fetched["result"]["filename"] == "reviews.csv"
    assert "expires_at" in fetched and "created_at" in fetched


def test_batch_job_get_returns_none_for_unknown_id(session):
    from app.repositories import batch_repository
    assert batch_repository.get_batch_job(session, "does-not-exist") is None


def test_cleanup_expired_jobs_removes_only_expired(session):
    from datetime import datetime, timedelta, timezone

    from app.repositories import batch_repository

    expired = BatchUploadJob(
        filename="old.csv", model_name="bert", text_column_used="text", rows_processed=1, n_positive=1, n_negative=0,
        result_json={}, created_at=datetime.now(timezone.utc) - timedelta(days=10),
        expires_at=datetime.now(timezone.utc) - timedelta(days=3),
    )
    fresh_id = batch_repository.save_batch_job(session, {"filename": "new.csv", "model_name": "bert", "text_column_used": "text", "rows_processed": 1, "n_positive": 1, "n_negative": 0})
    session.add(expired)
    session.commit()

    removed = batch_repository.cleanup_expired_jobs(session)
    assert removed >= 1
    assert batch_repository.get_batch_job(session, fresh_id) is not None


# --------------------------------------------------------------------------- #
# API round-trip: /predict persists, /analyses lists it, /feedback works
# --------------------------------------------------------------------------- #

def _bert_available(client) -> bool:
    status = client.get("/api/v1/models/status").json()["data"]
    return status["artifacts"].get("bert", {}).get("status") == "available"


def test_predict_persists_and_returns_analysis_id(client, db_available):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    resp = client.post("/api/v1/sentiment/predict", json={"text": "Excellent product, arrived early.", "model_name": "bert"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["analysis_id"] is not None
    assert len(data["analysis_id"]) == 32


def test_analysis_history_endpoint_returns_persisted_row(client, db_available):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    predict_resp = client.post("/api/v1/sentiment/predict", json={"text": "Terrible, broke immediately.", "model_name": "bert"})
    analysis_id = predict_resp.json()["data"]["analysis_id"]

    get_resp = client.get(f"/api/v1/sentiment/analyses/{analysis_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["text"] == "Terrible, broke immediately."

    list_resp = client.get("/api/v1/sentiment/analyses?limit=5")
    assert list_resp.status_code == 200
    assert list_resp.json()["data"]["total"] >= 1


def test_analysis_unknown_id_returns_404(client, db_available):
    resp = client.get("/api/v1/sentiment/analyses/does-not-exist")
    assert resp.status_code == 404


def test_feedback_round_trip_via_api(client, db_available):
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    predict_resp = client.post("/api/v1/sentiment/predict", json={"text": "It is fine I guess.", "model_name": "bert"})
    analysis_id = predict_resp.json()["data"]["analysis_id"]

    fb_resp = client.post(f"/api/v1/sentiment/analyses/{analysis_id}/feedback", json={"is_correct": False, "comment": "should be neutral"})
    assert fb_resp.status_code == 200
    assert fb_resp.json()["data"]["is_correct"] is False


def test_feedback_unknown_analysis_returns_404(client, db_available):
    resp = client.post("/api/v1/sentiment/analyses/does-not-exist/feedback", json={"is_correct": True})
    assert resp.status_code == 404


def test_history_endpoints_return_503_when_db_unconfigured(client, db_available, monkeypatch):
    """Confirms the explicit-history endpoints fail clearly (not silently
    empty) when DATABASE_URL isn't set -- the documented default state."""
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    resp = client.get("/api/v1/sentiment/analyses")
    assert resp.status_code == 503


def test_upload_file_persists_to_db_when_configured(client, db_available):
    """upload_store.py should transparently use the DB backend once
    DATABASE_URL is set -- same public function signatures, no caller changes."""
    if not _bert_available(client):
        pytest.skip("Fine-tuned BERT artifact not available in this environment.")
    csv_content = b"text\n\"Great product, highly recommend!\"\n"
    resp = client.post(
        "/api/v1/sentiment/upload-file",
        files={"file": ("reviews.csv", csv_content, "text/csv")},
        data={"model_name": "bert"},
    )
    assert resp.status_code == 200
    upload_id = resp.json()["data"]["upload_id"]

    from app.db.base import get_session_factory
    from app.repositories import batch_repository

    session = get_session_factory()()
    try:
        found = batch_repository.get_batch_job(session, upload_id)
        assert found is not None, "upload-file result should have been persisted to the DB, not just the local JSON store"
    finally:
        session.close()
