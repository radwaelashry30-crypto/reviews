"""Backend Model Information presentation contract (Checkpoint C). Read-only,
typed shape for the future visual Model page -- no frontend/chart work
happens here, only the backend data contract it will eventually consume.

Every field on every component below is sourced from an already-verified
project fact (artifacts/model_manifest.json, results/reproduced_metrics.json,
DEPLOYMENT.md, or the loader code's own docstrings) -- see
app/services/model_info_service.py::build_model_component_info for the exact
source of each value. Nothing here is invented; a field with no verified
source is left null rather than guessed (see DeBERTa's verified_metrics).
"""
from __future__ import annotations

from pydantic import BaseModel


class ModelProvenance(BaseModel):
    source_checkpoint: str | None = None
    is_configured_default: bool = False
    is_frontend_default: bool = False
    is_deployment_available_on_public_render: bool = True
    is_fallback: bool = False
    is_optional: bool = False
    evaluation_dataset: str | None = None
    evaluation_split: str | None = None
    evaluation_sample_size: int | None = None
    verified_metrics: dict | None = None
    verified_model_size_mb: float | None = None
    methodology_note: str | None = None
    last_checked_at: str | None = None


class ModelComponentInfo(BaseModel):
    component_id: str
    display_name: str
    purpose: str
    model_type: str
    status: str
    loading_strategy: str
    input_contract: str
    output_labels: list[str]
    limitations: str
    provenance: ModelProvenance
