# Project Structure

This document explains the role of every top-level directory and file in this
repository, and maps them against a generic ML-repo template for anyone
expecting `src/`, root-level `scripts/`, or `configs/*.yaml`.

## Why this layout, not a generic `src/` tree

This is a deployed FastAPI + React application, not a standalone modeling
package. The ML pipeline lives inside the backend it serves
(`backend/app/ml/`) so there is exactly one import path for every consumer —
API, tests, CLI scripts, and the walkthrough notebook all import the same
modules, instead of a `src/` package that the backend would have to
re-import or duplicate. `shared/` is the explicit contract that keeps
backend, frontend, and notebook from drifting apart. See `MODEL_CARD.md`,
`ARTIFACT_AUDIT.md`, and `PROJECT_JOURNEY.md` for how this shape emerged
from a 22-issue technical review, not as an initial design choice.

## Top level

| Path | Role |
|---|---|
| `backend/` | FastAPI application: API, ML pipeline, services, tests, migrations, CLI scripts |
| `frontend/` | React + TypeScript dashboard and inference UI (Vite, Vitest) |
| `shared/` | Cross-stack contract: `api_contract.json`, `label_mapping.json`, `model_manifest.json`, example API responses — the single source backend and frontend are both checked against |
| `models/` | Trained model artifacts: `bert_review_sentiment/`, `cnn2d_review_sentiment.pt`, `fake_review_detector*/` (DistilBERT + TF-IDF ensemble, see `MODEL_COMPARISON_AUDIT.md` §9) |
| `artifacts/` | Fitted preprocessing artifacts: tokenizer, RFM scaler/kmeans, label mapping, split manifest, translation manifest — everything inference needs besides model weights |
| `config/` | `bert_config.json`, `cnn2d_config.json`, `project_config.json` — training/inference hyperparameters and paths, consumed by `backend/scripts/*` and `backend/app/ml/*` |
| `data/` | `raw/` (original Olist CSVs), `interim/`, `processed/` (grain-correct enriched parquet datasets, see `DATA_GRAIN_AUDIT.md`), `external/` (Deceptive Opinion Spam Corpus), `uploads/` (runtime batch-upload files, gitignored in spirit — see `data/README.md`) |
| `results/` | Generated metrics, confusion matrices, audits, calibration analysis — JSON, regenerable via `backend/scripts/regenerate_metrics.py`, never hand-edited (`verify_metrics_freshness.py` is the CI guard against that drift) |
| `reports/` | `executive_analytics_report.md` — business-facing summary |
| `figures/` | Saved plots referenced by docs/notebook |
| `output/` | Legacy merged dataset kept for the original notebook's exact reproduction path |
| `notebooks/` | `olist_full_eda_preprocessing_PYTORCH.ipynb` — the original 151-cell research notebook, preserved as the historical baseline |
| `original_project_backup/` | Pre-refactor snapshot of the original notebook + its report, kept for audit traceability (never edited) |
| `Baseera_Project_Walkthrough.ipynb` | The current, maintained notebook — runnable end-to-end, imports from `backend.app.ml` rather than redefining the pipeline inline |
| `*.md` (root) | `README.md` (main entry point), `PROJECT_JOURNEY.md`/`.pdf` (chronological history of every phase and fix), `MODEL_CARD.md`, `MODEL_COMPARISON_AUDIT.md`, `DATA_LEAKAGE_AUDIT.md`, `DATA_GRAIN_AUDIT.md`, `DATA_QUALITY_AUDIT.md`, `ARTIFACT_AUDIT.md`, `API_DOCUMENTATION.md`, `FRONTEND_INTEGRATION.md`, `DATABASE_SETUP.md`, `DEPLOYMENT.md`, `TESTING.md`, `RELEASE_CHECKLIST.md`, `CHANGELOG.md` |
| `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` | Local/production container setup (multi-stage, CPU-only torch wheel — see `CHANGELOG.md` 2026-08-19) |
| `.github/workflows/ci.yml` | Backend tests, frontend typecheck/test/build, Docker build+boot |
| `.env.example` | Documented environment variables, no real secrets |

## Backend (`backend/app/`)

| Path | Role |
|---|---|
| `main.py` | App entry point, startup model loading, `_check_metrics_freshness()` |
| `api/` | FastAPI routers |
| `core/` | `config.py` (settings), `exceptions.py`, `logging.py`, `rate_limit.py`, `security.py` |
| `db/` | SQLAlchemy models + base (optional persistence, see `DATABASE_SETUP.md`) |
| `ml/` | **The single ML source of truth.** `cleaning.py`, `preprocessing.py`, `feature_engineering.py`, `data_loading.py`, `datasets.py`, `models.py` (BERT + CNN2D architectures), `training.py`, `evaluation.py`, `explainability.py` (SHAP), `segmentation.py` (RFM/K-Means), `absa.py` + `aspect_extraction.py`, `fake_review_detection.py`, `negation_augmentation.py`, `translation.py`, `eda.py`, `utils.py` |
| `repositories/` | Data-access layer (analytics, artifacts, batch, sentiment) |
| `schemas/` | Pydantic request/response models — the Python side of `shared/api_contract.json` |
| `services/` | Business logic orchestration between API and `ml/` |
| `tests/` | 20 pytest files — leakage, data-grain, model registry, rate limiting, CORS, batch upload, fake-review stability, etc. (136 tests, all passing as of this audit) |
| `migrations/` | Alembic migrations |
| `scripts/` | CLI entry points: `train.py`, `evaluate.py`, `inference.py`, `run_pipeline.py`, `run_eda.py`, `regenerate_metrics.py`, `export_artifacts.py` (artifact discovery/validation), `verify_metrics_freshness.py`, `check_no_local_paths.py`, plus the fake-review training/testing/stability scripts |
| `requirements.txt` / `requirements-dev.txt` | Runtime-only vs. training/test/analysis dependencies, split so the production image doesn't pay for dev tooling (see comments in the file itself for the incident that motivated the split) |

## Frontend (`frontend/src/`)

`api/` (typed HTTP clients), `components/` (charts, dashboard, sentiment, batch, ui, app-shell, landing), `hooks/`, `pages/`, `styles/`, `test/` (Vitest setup), `types/` (`api.ts`, `analytics.ts`, `sentiment.ts`, `segmentation.ts` — the TypeScript side of `shared/api_contract.json`), `utils/`.

## Mapping to a generic template (for reference)

| Generic template asks for | This repo's equivalent |
|---|---|
| `src/preprocessing/`, `src/models/`, `src/training/`, `src/evaluation/`, `src/inference/` | `backend/app/ml/*.py` |
| `src/utils/config.py`, `paths.py` | `backend/app/core/config.py`, `config/*.json` |
| `scripts/train_model.py`, `evaluate_model.py`, `run_inference.py` | `backend/scripts/train.py`, `evaluate.py`, `inference.py` |
| `scripts/validate_artifacts.py` | `backend/scripts/export_artifacts.py --discover` + `verify_metrics_freshness.py` |
| `configs/*.yaml` | `config/*.json` (same role, JSON instead of YAML — consumed the same way by scripts) |
| `artifacts/models/`, `preprocessors/`, `tokenizers/` | `models/`, `artifacts/` |
| `tests/test_training_inference_parity.py` | `backend/app/tests/test_no_eval_leakage.py`, `test_data_grain.py`, `test_evaluation.py` cover this in practice; no single file is named identically |
| `.env.example`, `pyproject.toml` | `.env.example` exists; dependency management uses `requirements.txt`/`requirements-dev.txt` (Python) + `package.json` (frontend) rather than `pyproject.toml` — consistent with how `backend/Dockerfile` and CI already install |
