"""Guards shared by every marketplace persistence module.

The marketplace-data feature is PostgreSQL-only (JSONB columns, a partial
unique index enforcing "at most one active version", and
pg_advisory_xact_lock for activation serialization -- see
marketplace_version_service.py). The existing sentiment/batch persistence
layer (app/db/base.py) intentionally also supports a local SQLite file so
the rest of the app keeps working with zero setup; marketplace writes must
fail clearly instead of silently behaving differently on SQLite.
"""
from __future__ import annotations

from app.core.exceptions import AppError
from app.db.base import db_configured, get_engine
from fastapi import status


class MarketplaceUnavailableError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="MARKETPLACE_DB_UNAVAILABLE", status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details)


def require_postgres() -> None:
    """Raises MarketplaceUnavailableError unless DATABASE_URL is configured
    and its driver dialect is genuinely PostgreSQL. Call this at the top of
    every marketplace repository/service entry point -- never assume."""
    if not db_configured():
        raise MarketplaceUnavailableError(
            "Marketplace data management requires a configured PostgreSQL database (DATABASE_URL is not set)."
        )
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        raise MarketplaceUnavailableError(
            f"Marketplace data management requires PostgreSQL; the configured DATABASE_URL uses '{engine.dialect.name}'."
        )
