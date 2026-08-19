"""FastAPI application entry point.

Run from the `backend/` directory with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import register_rate_limiter
from app.repositories.analytics_repository import AnalyticsRepository
from app.services.model_registry import ModelRegistry

configure_logging()
logger = get_logger(__name__)


def _run_pending_migrations() -> None:
    """Applies Alembic migrations against DATABASE_URL on startup.

    Render (and most simple deploy targets here) have no separate release/
    migration step -- the only process that ever gets network access to the
    real database is this app itself. Without this, a fresh database has
    DATABASE_URL configured and connects fine (so /health looks healthy) but
    has no tables, so every write silently fails inside the best-effort
    persistence layer (see app/services/persistence_service.py). Wrapped in
    try/except so a migration problem degrades to "no persistence", same as
    an unreachable database, rather than crashing the whole app.
    """
    try:
        from alembic import command
        from alembic.config import Config

        backend_dir = Path(__file__).resolve().parents[1]
        cfg = Config(str(backend_dir / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_dir / "migrations"))
        command.upgrade(cfg, "head")
        logger.info("Database: configured, migrations applied (up to date)")
    except Exception as e:
        logger.warning("Database: configured, but migration step failed (persistence may not work): %s", e)


def _check_metrics_freshness() -> None:
    """Warns loudly at startup if results/reproduced_metrics.json describes a
    different BERT checkpoint than the one actually on disk -- the exact
    failure mode a retraining run caused once already (a checkpoint was
    overwritten without regenerating the published metrics that describe
    it). Never raises; a missing/unreadable metrics file just means there's
    nothing to compare yet."""
    try:
        import json

        from app.ml.utils import checkpoint_fingerprint

        metrics_path = settings.RESULTS_DIR / "reproduced_metrics.json"
        if not metrics_path.is_file():
            return
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        recorded = metrics.get("bert", {}).get("checkpoint_sha256")
        current = checkpoint_fingerprint(settings.BERT_MODEL_PATH)
        if recorded and current and recorded != current:
            logger.error(
                "STALE METRICS: results/reproduced_metrics.json describes BERT checkpoint "
                "%s, but the checkpoint on disk is %s. Re-run scripts/regenerate_metrics.py.",
                recorded, current,
            )
    except Exception as e:
        logger.warning("Metrics freshness check failed (non-fatal): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)

    registry = ModelRegistry()
    registry.load_all()
    app.state.model_registry = registry
    for name, status in registry.statuses.items():
        logger.info("Artifact '%s': %s", name, status.status)

    repo = AnalyticsRepository()
    repo.load_all()
    app.state.analytics_repository = repo
    logger.info("Loaded analytics datasets: %s", repo.available_datasets())
    logger.info("Loaded analytics results: %s", repo.available_results())

    _check_metrics_freshness()

    from app.db.base import db_configured

    if db_configured():
        _run_pending_migrations()
    else:
        logger.info("Database: not configured (predictions/uploads persist locally only)")

    yield

    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Olist Marketplace end-to-end analytics and review-sentiment intelligence API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
register_rate_limiter(app)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
    logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api_prefix": settings.API_V1_PREFIX,
    }
