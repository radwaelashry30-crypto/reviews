"""Shared, side-effect-free helpers used across the ML pipeline.

Extracted from the "Utility Functions" section of the original notebook
(olist_full_eda_preprocessing_PYTORCH.ipynb, cells 8-15). Kept dependency-light:
no FastAPI, no notebook globals, no implicit device or seed state.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_SEED = 42


def set_seed(seed: int = DEFAULT_SEED) -> None:
    """Fix Python/NumPy/PyTorch (CPU+CUDA) RNG state. Notebook cell 11, unchanged."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass


def get_device(prefer_gpu: bool = True) -> "Any":
    """Return a torch.device, CUDA if available and requested, else CPU."""
    import torch

    if prefer_gpu and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def checkpoint_fingerprint(model_dir: Path) -> str | None:
    """SHA-256 over a model directory's weight files, truncated to 16 hex
    chars -- changes with any retraining. Used to detect when a published
    results/*.json file describes a different checkpoint than the one
    actually on disk (a real bug found in this project: metrics files went
    stale after a retraining run overwrote the checkpoint without
    regenerating them). Returns None if the directory has no recognized
    weight files (e.g. not yet trained/exported)."""
    model_dir = Path(model_dir)
    weight_files = sorted(model_dir.glob("*.safetensors")) or sorted(model_dir.glob("pytorch_model.bin")) or sorted(model_dir.glob("*.pt"))
    if not weight_files:
        return None
    h = hashlib.sha256()
    for p in weight_files:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()[:16]


def optimize_dtypes(d: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    """Downcast float64/int64 columns. Notebook cell 10, unchanged behavior."""
    before = d.memory_usage(deep=True).sum() / 1024**2

    for col in d.select_dtypes(include="float64").columns:
        d[col] = pd.to_numeric(d[col], downcast="float")

    for col in d.select_dtypes(include="int64").columns:
        d[col] = pd.to_numeric(d[col], downcast="integer")

    after = d.memory_usage(deep=True).sum() / 1024**2
    return d, before, after


def stable_text_hash(text: str) -> str:
    """Deterministic identifier for a piece of review text (used as a stable row id)."""
    normalized = normalize_text_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def normalize_text_for_hash(text: str) -> str:
    """Lowercase + collapse whitespace, for duplicate detection and hashing.

    Deliberately conservative: this is used to detect near-duplicate review
    text (e.g. differing only in surrounding whitespace or case) before
    dataset splitting, per the leakage-audit requirement to normalize text
    before deduplication rather than relying on exact byte equality alone.
    """
    return " ".join(str(text).strip().lower().split())


class JSONSafeEncoder(json.JSONEncoder):
    """Encoder that converts NumPy/Pandas scalars and NaN/Inf to JSON-safe values."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            v = float(o)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (pd.Timestamp, datetime)):
            return o.isoformat()
        if isinstance(o, Path):
            return str(o)
        return super().default(o)


def to_json_safe(obj: Any) -> Any:
    """Recursively convert a Python object into JSON-safe primitives.

    Replaces NaN/Infinity with None (invalid in strict JSON) and converts
    NumPy/Pandas scalar types to native Python types.
    """
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return to_json_safe(obj.tolist())
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, Path):
        return str(obj)
    return obj


def write_json(path: str | Path, payload: dict, schema_version: str = "1.0") -> None:
    """Write a JSON-safe results file with generation metadata attached."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema_version,
        **to_json_safe(payload),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, allow_nan=False)


BRAZIL_STATE_NAMES: dict[str, str] = {
    "SP": "São Paulo", "MG": "Minas Gerais", "ES": "Espírito Santo", "RS": "Rio Grande do Sul",
    "DF": "Distrito Federal", "PR": "Paraná", "SC": "Santa Catarina", "RJ": "Rio de Janeiro",
    "GO": "Goiás", "BA": "Bahia", "MA": "Maranhão", "PB": "Paraíba", "PE": "Pernambuco",
    "CE": "Ceará", "MT": "Mato Grosso", "PI": "Piauí", "RN": "Rio Grande do Norte",
    "MS": "Mato Grosso do Sul", "PA": "Pará", "AM": "Amazonas", "SE": "Sergipe",
    "RO": "Rondônia", "RR": "Roraima", "TO": "Tocantins", "AP": "Amapá",
    "AL": "Alagoas", "AC": "Acre",
}

BRAZIL_MACRO_REGION: dict[str, str] = {
    "SP": "Southeast", "RJ": "Southeast", "MG": "Southeast", "ES": "Southeast",
    "PR": "South", "SC": "South", "RS": "South",
    "BA": "Northeast", "PE": "Northeast", "CE": "Northeast", "MA": "Northeast",
    "PB": "Northeast", "RN": "Northeast", "AL": "Northeast", "SE": "Northeast", "PI": "Northeast",
    "GO": "Central-West", "MT": "Central-West", "MS": "Central-West", "DF": "Central-West",
    "AM": "North", "PA": "North", "RO": "North", "AC": "North", "AP": "North", "RR": "North", "TO": "North",
}


def state_code_to_name(code: str) -> str:
    """Map a 2-letter Brazilian state code to its full name; passthrough if already full."""
    return BRAZIL_STATE_NAMES.get(code, code)


def state_name_to_region(state_name_or_code: str) -> str | None:
    """Map either a 2-letter code or a full state name to its IBGE macro-region."""
    if state_name_or_code in BRAZIL_MACRO_REGION:
        return BRAZIL_MACRO_REGION[state_name_or_code]
    reverse = {v: k for k, v in BRAZIL_STATE_NAMES.items()}
    code = reverse.get(state_name_or_code)
    return BRAZIL_MACRO_REGION.get(code) if code else None
