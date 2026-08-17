"""SQLAlchemy engine/session setup. Entirely optional infrastructure --
mirrors the ENABLE_BERT / ALLOW_EXTERNAL_MODEL_DOWNLOADS pattern already used
elsewhere in this project: the app must run correctly with `DATABASE_URL`
unset (no persistence, but no crash), and degrade gracefully if the database
is unreachable at request time (never break a prediction because history
couldn't be saved).
"""
from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker | None = None


def db_configured() -> bool:
    return bool(settings.DATABASE_URL)


def get_engine():
    """Lazily creates the engine on first use, not at import time (so a
    missing/unreachable DB never breaks app startup)."""
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured.")
        # pool_pre_ping avoids serving a request against a connection the DB
        # server already dropped (common on free-tier hosts that idle-close
        # connections) -- fails fast with a clean reconnect instead of a
        # confusing mid-query error.
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_db_session() -> Session:
    """FastAPI dependency for endpoints that ARE explicitly about DB-backed
    history (e.g. GET /sentiment/analyses) -- these should fail clearly
    (503, via the caller checking db_configured() first) rather than
    silently return nothing when the database isn't configured."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def check_db_connection() -> tuple[bool, str | None]:
    """Used by the /health endpoint. Never raises -- returns (ok, error)."""
    if not db_configured():
        return False, "DATABASE_URL not configured"
    try:
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        logger.warning("Database health check failed: %s", e)
        return False, str(e)
