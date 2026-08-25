"""Shared fixtures for the repository-level structural tests (tests/), as
distinct from backend/app/tests/ (the backend's own application test suite,
run separately via `cd backend && pytest`)."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def backend_on_path() -> Path:
    """Adds backend/ to sys.path once per session, mirroring exactly what
    notebooks/Baseera_Main_Notebook_Final.ipynb's Section 0.2 does, so
    `import app...` resolves the same way in tests as it does for the
    notebook and the backend's own entry point."""
    backend_dir = REPO_ROOT / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    return backend_dir
