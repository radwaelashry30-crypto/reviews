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


def _read_json(path):
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@router.get("/info")
def model_info():
    manifest = _read_json(settings.ARTIFACT_DIR / "model_manifest.json") or {
        "note": "model_manifest.json not found; run export_artifacts.py"
    }

    # reproduced_metrics.json (genuine forward-pass inference on the
    # corrected, leakage-free split) is the metrics source of truth.
    # notebook_reported_metrics.json is the ORIGINAL notebook's numbers,
    # which DATA_LEAKAGE_AUDIT.md proved were computed on a split that
    # leaked 1,097 duplicate review texts across train/val/test -- serving
    # those to users as if they were current was a real bug (see the
    # project's technical review). Kept only as a clearly-invalid historical
    # reference, never as "metrics".
    reproduced = _read_json(settings.RESULTS_DIR / "reproduced_metrics.json")
    notebook = _read_json(settings.RESULTS_DIR / "notebook_reported_metrics.json")

    return envelope({
        "manifest": manifest,
        "metrics": reproduced,
        "historical_notebook_metrics": {
            "values": notebook,
            "valid": False,
            "reason": (
                "Computed on the notebook's original split, which leaked 1,097 duplicate "
                "review texts across train/val/test. Retained for audit trail only -- do not cite."
            ),
        },
        "label_mapping": {"Negative": 0, "Positive": 1},
        "limitations": (
            "Sentiment predictions are probabilistic and dataset-dependent. "
            "They estimate review sentiment, not objective truth. See "
            "MODEL_COMPARISON_AUDIT.md and DATA_LEAKAGE_AUDIT.md for evaluation caveats."
        ),
    })
