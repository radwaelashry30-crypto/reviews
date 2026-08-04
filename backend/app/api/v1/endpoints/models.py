from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.dependencies import get_model_registry
from app.schemas.common import envelope
from app.services.model_registry import ModelRegistry

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status")
def model_status(registry: ModelRegistry = Depends(get_model_registry)):
    return envelope(registry.status_report())


@router.get("/info")
def model_info():
    manifest_path = settings.ARTIFACT_DIR / "model_manifest.json"
    if manifest_path.is_file():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {"note": "model_manifest.json not found; run export_artifacts.py"}

    metrics_path = settings.RESULTS_DIR / "notebook_reported_metrics.json"
    reported = None
    if metrics_path.is_file():
        with open(metrics_path, encoding="utf-8") as f:
            reported = json.load(f)

    return envelope({
        "manifest": manifest,
        "notebook_reported_metrics": reported,
        "label_mapping": {"Negative": 0, "Positive": 1},
        "limitations": (
            "Sentiment predictions are probabilistic and dataset-dependent. "
            "They estimate review sentiment, not objective truth. See "
            "MODEL_COMPARISON_AUDIT.md and DATA_LEAKAGE_AUDIT.md for evaluation caveats."
        ),
    })
