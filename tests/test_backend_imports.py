"""Verifies the backend application is importable and constructible after
restructuring, without starting a live server or sending any external
request -- catches broken imports/paths from moving files without needing
to run the full backend/app/tests/ suite (which needs model artefacts and,
for some tests, a database)."""


def test_backend_app_module_importable(backend_on_path):
    import app.main  # noqa: F401  -- import success is the assertion


def test_fastapi_app_object_exists(backend_on_path):
    from app.main import app

    assert app is not None
    assert app.title  # FastAPI app was constructed with some title


def test_core_config_loads_without_network_or_db(backend_on_path):
    from app.core.config import settings

    assert settings.APP_NAME
    assert settings.API_V1_PREFIX.startswith("/")


def test_ml_module_importable(backend_on_path):
    """backend/app/ml/ is this project's single ML source of truth (see
    docs/architecture/PROJECT_STRUCTURE.md) -- both the backend and
    notebooks/Baseera_Main_Notebook_Final.ipynb's Appendix import from here,
    so it must resolve cleanly on its own."""
    import app.ml.data_loading  # noqa: F401
    import app.ml.preprocessing  # noqa: F401
