import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The rate limiter's in-memory quota is process-wide and the `client`
    fixture is session-scoped, so without a reset, one test's requests count
    against every other test's quota against the same endpoint. Reset before
    each test so rate-limit tests (and every other test hitting a limited
    endpoint more than once) stay independent."""
    limiter.reset()
    yield


@pytest.fixture(scope="session")
def project_root() -> Path:
    return BACKEND_DIR.parent
