"""Data-access layer for sentiment_analyses / aspects / feedback.

Every write function here is called "best-effort" from the API layer -- a
database write failure must never break a prediction response. Callers wrap
these in try/except (see app/api/v1/endpoints/sentiment.py); this module
itself stays a plain, testable data-access layer with no swallowed
exceptions, so failures are still visible to tests and logs.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PredictionFeedback, SentimentAnalysis, SentimentAnalysisAspect


def save_analysis(
    session: Session,
    *,
    text: str,
    prediction: dict[str, Any],
    aspects: list[dict[str, Any]] | None = None,
    idempotency_key: str | None = None,
) -> SentimentAnalysis:
    """Persists one sentiment prediction (and optional Task-3 aspect rows)
    in a single transaction. `prediction` is the dict shape returned by
    sentiment_service.predict_sentiment(); `aspects` is the
    `aspects.aspects` list from advanced_sentiment_service.run_full_pipeline()
    when available."""
    row = SentimentAnalysis(
        text=text,
        cleaned_text=prediction["cleaned_text"],
        label=prediction["label"],
        class_id=prediction["class_id"],
        probability_positive=prediction["probability_positive"],
        probability_negative=prediction["probability_negative"],
        confidence=prediction["confidence"],
        model_name=prediction["model_name"],
        source_language=prediction["source_language"],
        translated=prediction["translated"],
        idempotency_key=idempotency_key,
    )
    if aspects:
        row.aspects = [
            SentimentAnalysisAspect(aspect=a["aspect"], sentiment=a["sentiment"], confidence=a["confidence"])
            for a in aspects
        ]
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_analysis(session: Session, analysis_id: str) -> SentimentAnalysis | None:
    return session.get(SentimentAnalysis, analysis_id)


def get_by_idempotency_key(session: Session, idempotency_key: str) -> SentimentAnalysis | None:
    return session.execute(
        select(SentimentAnalysis).where(SentimentAnalysis.idempotency_key == idempotency_key)
    ).scalar_one_or_none()


def list_analyses(
    session: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    label: str | None = None,
    model_name: str | None = None,
) -> tuple[list[SentimentAnalysis], int]:
    """Returns (rows, total_count_matching_filters) for pagination."""
    stmt = select(SentimentAnalysis)
    count_stmt = select(func.count()).select_from(SentimentAnalysis)
    if label:
        stmt = stmt.where(SentimentAnalysis.label == label)
        count_stmt = count_stmt.where(SentimentAnalysis.label == label)
    if model_name:
        stmt = stmt.where(SentimentAnalysis.model_name == model_name)
        count_stmt = count_stmt.where(SentimentAnalysis.model_name == model_name)

    total = session.execute(count_stmt).scalar_one()
    rows = session.execute(
        stmt.order_by(SentimentAnalysis.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return list(rows), total


def save_feedback(
    session: Session, *, analysis_id: str, is_correct: bool, comment: str | None = None,
) -> PredictionFeedback | None:
    """Returns None (does not raise) if analysis_id doesn't exist -- the
    caller turns that into a clean 404."""
    if get_analysis(session, analysis_id) is None:
        return None
    row = PredictionFeedback(analysis_id=analysis_id, is_correct=is_correct, comment=comment)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
