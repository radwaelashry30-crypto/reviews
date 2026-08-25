"""In-memory cache of the ACTIVE marketplace dataset version's compact
derived artifacts only -- never the large typed entity tables (those stay
database-query-backed, see marketplace_repository.list_*_analytics).

Loaded once at startup (bounded: a handful of small JSONB SELECTs, the same
cost class as AnalyticsRepository.load_all()'s existing synchronous startup
read of results/*.json -- NOT a rebuild from raw canonical rows, see
Checkpoint B correction #6) and reloaded after every successful activation.
The swap is atomic: a new _MarketplaceCacheState is built completely off to
the side, then assigned to the single `state` attribute in one step -- a
concurrent reader either sees the old, complete state or the new, complete
state, never a half-populated one.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import settings
from app.db.base import check_db_connection, db_configured, get_session_factory
from app.repositories import marketplace_repository as repo

logger = logging.getLogger(__name__)

READINESS_STATES = ("healthy", "analytics_loading", "ready", "degraded", "database_unavailable")


@dataclass(frozen=True)
class MarketplaceCacheState:
    readiness: str  # one of READINESS_STATES ('healthy' is not used here -- see health.py, this cache never reports it)
    source: str  # 'marketplace_active' | 'historical_packaged'
    active_version_id: str | None = None
    artifacts: dict = field(default_factory=dict)
    error: str | None = None


class MarketplaceAnalyticsCache:
    def __init__(self) -> None:
        self.state = MarketplaceCacheState(readiness="ready", source="historical_packaged")

    def load_active(self) -> None:
        """Bounded, synchronous, safe to call in the blocking lifespan
        startup path -- see main.py. Never raises; any failure degrades to
        the historical_packaged fallback state instead of crashing startup."""
        if not db_configured():
            self.state = MarketplaceCacheState(readiness="ready", source="historical_packaged")
            return

        ok, error = check_db_connection()
        if not ok:
            logger.warning("Marketplace analytics cache: database unavailable (%s) -- serving historical_packaged fallback.", error)
            self.state = MarketplaceCacheState(readiness="database_unavailable", source="historical_packaged", error=error)
            return

        session = get_session_factory()()
        try:
            active = repo.get_active_version(session)
            if active is None:
                self.state = MarketplaceCacheState(readiness="ready", source="historical_packaged")
                return

            artifacts = repo.list_derived_artifacts(session, active.id)
            missing = [a for a in repo.REQUIRED_ARTIFACTS if a not in artifacts]
            if missing:
                logger.error(
                    "Marketplace analytics cache: active version %s is missing required artifacts %s -- "
                    "serving historical_packaged fallback rather than an incomplete active dataset.",
                    active.id, missing,
                )
                self.state = MarketplaceCacheState(
                    readiness="degraded", source="historical_packaged",
                    error=f"active version missing artifacts: {missing}",
                )
                return

            self.state = MarketplaceCacheState(
                readiness="ready", source="marketplace_active", active_version_id=active.id, artifacts=artifacts,
            )
        except Exception as e:
            logger.warning("Marketplace analytics cache: load failed (%s) -- serving historical_packaged fallback.", e)
            self.state = MarketplaceCacheState(readiness="degraded", source="historical_packaged", error=str(e))
        finally:
            session.close()

    def get_artifact(self, name: str) -> dict | None:
        return self.state.artifacts.get(name)

    def readiness_report(self) -> dict:
        return {
            "readiness": self.state.readiness,
            "source": self.state.source,
            "active_version_id": self.state.active_version_id,
            "error": self.state.error,
        }
