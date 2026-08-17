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


def try_save_analysis(text: str, prediction: dict[str, Any], aspects: list[dict[str, Any]] | None = None) -> str | None:
    if not db_configured():
        return None
    try:
        from app.repositories import sentiment_repository

        session = get_session_factory()()
        try:
            row = sentiment_repository.save_analysis(session, text=text, prediction=prediction, aspects=aspects)
            return row.id
        finally:
            session.close()
    except Exception as e:
        logger.warning("Best-effort analysis persistence failed (prediction still returned normally): %s", e)
        return None
