"""Read-only helpers for reporting artifact metadata (sizes, paths) without loading them."""
from __future__ import annotations

from pathlib import Path


def describe_path(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "path_relative": _relative(path)}
    if path.is_dir():
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    else:
        size = path.stat().st_size
    return {"exists": True, "path_relative": _relative(path), "size_bytes": size, "size_mb": round(size / 1024**2, 2)}


def _relative(path: Path) -> str:
    try:
        from app.core.config import PROJECT_ROOT

        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
