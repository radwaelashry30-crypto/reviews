"""Best-effort persistence helpers for the sentiment endpoints. Every
function here swallows its own exceptions and logs a warning -- a database
write failure must never turn a working prediction into a 500. Returns None
on any failure (DB not configured, DB unreachable, etc.) so callers can
simply do `analysis_id = try_save_analysis(...)` and include it in the
response only when persistence actually happened.
"""
from __future__ import annotations

import logging
from typing import Any

from app.db.base import db_configured, get_session_factory

logger = logging.getLogger(__name__)


def try_save_analysis(
    text: str, prediction: dict[str, Any], aspects: list[dict[str, Any]] | None = None,
    idempotency_key: str | None = None,
) -> str | None:
    if not db_configured():
        return None
    try:
        from app.repositories import sentiment_repository

        session = get_session_factory()()
        try:
            row = sentiment_repository.save_analysis(
                session, text=text, prediction=prediction, aspects=aspects, idempotency_key=idempotency_key,
            )
            return row.id
        finally:
            session.close()
    except Exception as e:
        logger.warning("Best-effort analysis persistence failed (prediction still returned normally): %s", e)
        return None


def get_by_idempotency_key(idempotency_key: str) -> dict[str, Any] | None:
    """Returns the previously-saved prediction result for this key, or None
    if not configured/not found/on any error -- same best-effort contract as
    try_save_analysis. A miss just means "proceed normally, compute fresh"."""
    if not db_configured():
        return None
    try:
        from app.repositories import sentiment_repository

        session = get_session_factory()()
        try:
            row = sentiment_repository.get_by_idempotency_key(session, idempotency_key)
            if row is None:
                return None
            return {
                "label": row.label, "class_id": row.class_id,
                "probability_positive": row.probability_positive, "probability_negative": row.probability_negative,
                "confidence": row.confidence, "model_name": row.model_name,
                "source_language": row.source_language, "translated": row.translated,
                "cleaned_text": row.cleaned_text, "analysis_id": row.id,
            }
        finally:
            session.close()
    except Exception as e:
        logger.warning("Idempotency-key lookup failed (proceeding as a fresh request): %s", e)
        return None
