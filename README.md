# Baseera — Olist Marketplace Analytics and Customer Sentiment Intelligence

An academic and business analytics platform: a FastAPI backend, a React/TypeScript
frontend, and a PyTorch sentiment/explainability pipeline, all built on the public
[Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(2016–2018). **This is demonstrated using a public research dataset, not client-owned
data** — every chart and prediction runs against a fixed, static processed snapshot
(`data/processed/*.parquet`) or a request-time model call; there is no live/streaming
data source or scheduled refresh pipeline.

> **New here?**
> - [`docs/academic/PROJECT_JOURNEY.md`](docs/academic/PROJECT_JOURNEY.md) ([PDF](docs/academic/PROJECT_JOURNEY.pdf)) — every phase of work, every problem found, and the fix applied and verified for each, in chronological order.
> - [`notebooks/Baseera_Main_Notebook_Final.ipynb`](notebooks/Baseera_Main_Notebook_Final.ipynb) — the current, portability-tested notebook: Colab/local runtime detection, dependency-compatibility bootstrap, Kaggle dataset acquisition, an optional smoke-test mode, and the full EDA → preprocessing → modelling → evaluation → explainability pipeline. See [`docs/notebook/NOTEBOOK_RUN_GUIDE.md`](docs/notebook/NOTEBOOK_RUN_GUIDE.md).

## Contents

1. [Scope](#1-scope) · 2. [Business problem](#2-business-problem) · 3. [Dataset](#3-dataset) · 4. [Architecture overview](#4-architecture-overview) · 5. [Repository structure](#5-repository-structure) · 6. [Installation](#6-installation) · 7. [Running the notebook](#7-running-the-notebook-local--colab) · 8. [Backend](#8-backend) · 9. [Frontend](#9-frontend) · 10. [Full application launch](#10-full-application-launch) · 11. [Smoke-test mode](#11-smoke-test-mode) · 12. [Models and artefacts](#12-models-and-artefacts) · 13. [Environment variables](#13-environment-variables) · 14. [Testing](#14-testing) · 15. [Deployment](#15-deployment) · 16. [Academic documentation](#16-academic-documentation) · 17. [Presentation](#17-presentation) · 18. [Limitations](#18-limitations) · 19. [Responsible AI](#19-responsible-ai) · 20. [Licence](#20-licence) · 21. [Contributors](#21-contributors)

## 1. Scope

- **Sentiment classification** — binary Positive/Negative review sentiment (BERT and a from-scratch CNN2D, both genuinely trained and verified).
- **Aspect-based sentiment analysis (ABSA)** — sentiment-given-aspect across delivery, product quality, price, customer service, and packaging.
- **Explainable AI** — SHAP token-level explanations for individual predictions.
- **Business review analytics** — KPIs, RFM customer segmentation, delivery/payment/geography breakdowns, backed by a grain-correct relational data pipeline.

This project intentionally does **not** include fake-review/authenticity detection or
recommendation-system functionality — both were evaluated during earlier project phases
and removed; see `docs/academic/PROJECT_JOURNEY.md` and `CHANGELOG.md` for the history,
and do not reintroduce them.

## 2. Business problem

Olist is a Brazilian e-commerce marketplace. This project answers: how is the
marketplace performing (orders, revenue, delivery, payments), which
customers/sellers/categories need attention, and can a review's text alone flag its
sentiment automatically instead of waiting on the star rating?

## 3. Dataset

[Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(Kaggle identifier `olistbr/brazilian-ecommerce`, licensed CC BY-NC-SA 4.0) — 9
relational CSVs: orders, customers, order items, payments, reviews, products, sellers,
geolocation, category translation. This is a **public research dataset used for
demonstration purposes — it is not client-owned data**, and this project's derived
models/datasets inherit its non-commercial, share-alike, attribution-required licence.
See [`data/README.md`](data/README.md) for schemas, required filenames, and placement.

```
orders --(customer_id)--> customers
orders --(order_id, 1:N)--> order_items --(product_id)--> products --(category)--> translation
order_items --(seller_id)--> sellers
orders --(order_id, aggregated 1:1)--> payments_summary, review_summary
```

**Data-quality process**: 261,831 duplicate geolocation rows removed; missing delivery
dates deliberately kept as `NaT` (never fabricated) for cancelled/undelivered orders;
missing review text filled with an explicit `'No Message'` sentinel; price outliers
flagged (IQR), never silently dropped. Full detail:
[`docs/architecture/DATA_QUALITY_AUDIT.md`](docs/architecture/DATA_QUALITY_AUDIT.md).

**Data-grain audit (critical)**: the original notebook's single merged dataframe is at
**order-item grain** (112,650 rows, 98,666 unique orders — a 14.2% inflation on any
row-count KPI). This project provides grain-correct canonical datasets
(`orders_enriched`, `order_items_enriched`, `reviews_enriched`, `customers_enriched`,
`sellers_enriched`) and uses the right one for every KPI. Full detail:
[`docs/architecture/DATA_GRAIN_AUDIT.md`](docs/architecture/DATA_GRAIN_AUDIT.md).

## 4. Architecture overview

A relational data-engineering pipeline (9 raw tables → grain-correct enriched
datasets) feeds business KPIs, RFM segmentation, and the sentiment/ABSA models. A
FastAPI backend serves everything through a layered design
(`api` → `services` → `ml`/`repositories`), and a React + TypeScript frontend
consumes it. See [`docs/architecture/PROJECT_STRUCTURE.md`](docs/architecture/PROJECT_STRUCTURE.md)
for the full rationale, including why the ML pipeline lives inside
`backend/app/ml/` (one import path for API, tests, scripts, and the notebook) rather
than a separate top-level `src/` package.

**Models**: BERT (fine-tuned `LiYuan/amazon-review-sentiment-analysis`,
multilingual, `epochs=3`, `lr=2e-5`, seed 42) and CNN2D (from-scratch PyTorch,
multi-branch n-gram convolution, `epochs=10`, `lr=1e-3`, seed 42) — both trained on
the identical, deduplicated, leak-free split (see
[`docs/architecture/DATA_LEAKAGE_AUDIT.md`](docs/architecture/DATA_LEAKAGE_AUDIT.md)
and [`docs/architecture/MODEL_COMPARISON_AUDIT.md`](docs/architecture/MODEL_COMPARISON_AUDIT.md)
for why a fair, identical-split comparison mattered). Verified, reproduced metrics on
the corrected 6,297-row test set:

| | BERT | CNN2D |
|---|---|---|
| Accuracy | 0.9370 | 0.9201 |
| F1 (macro) | 0.9303 | 0.9127 |
| ROC-AUC | 0.9797 | 0.9676 |
| MCC | 0.8611 | 0.8276 |

Full architecture and hyperparameter detail:
[`docs/academic/MODEL_CARD.md`](docs/academic/MODEL_CARD.md). Reproduced numbers:
`results/reproduced_metrics.json`; regenerate after any retraining with
`cd backend && python scripts/regenerate_metrics.py` — never hand-edit these files.

## 5. Repository structure

```
baseera-marketplace-analytics/
├── backend/              FastAPI app: API, ML pipeline (app/ml/), services, tests, migrations, scripts
├── frontend/             React + TypeScript dashboard/inference UI (Vite, Vitest)
├── notebooks/
│   ├── Baseera_Main_Notebook_Final.ipynb   the current, portable, validated notebook
│   └── archive/                             historical notebooks — see notebooks/archive/README.md
├── models/                bert_review_sentiment/, cnn2d_review_sentiment.pt — see models/README.md
├── artifacts/              fitted tokenisers, scalers, manifests — see artifacts/README.md
├── data/                    raw/ (gitignored, see data/README.md), interim/, processed/, sample/
├── shared/                   cross-stack contract: api_contract.json, label_mapping.json, model_manifest.json
├── config/                    training/inference hyperparameters and paths (JSON)
├── results/                    generated metrics, confusion matrices, audits — regenerable, never hand-edited
├── reports/                     executive_analytics_report.md — business-facing summary
├── figures/                      saved EDA/model/SHAP/segmentation plots
├── docs/
│   ├── notebook/                  NOTEBOOK_RUN_GUIDE.md, NOTEBOOK_VALIDATION_REPORT.md
│   ├── academic/                   PROJECT_JOURNEY.md/.pdf, MODEL_CARD.md
│   └── architecture/                 PROJECT_STRUCTURE.md, API_DOCUMENTATION.md, all audits, DEPLOYMENT.md, TESTING.md, ...
├── tests/                          repository-level structural tests (see backend/app/tests/ for the application suite)
├── output/                          legacy order-item-grain export (original notebook reproduction only)
├── .github/workflows/                CI: backend tests, frontend typecheck/test/build, Docker build+boot
├── README.md, CHANGELOG.md, pyproject.toml, requirements.txt, requirements-notebook.txt
├── run_project.bat / run_project.sh    local launcher (Windows / macOS-Linux)
└── docker-compose.yml, .env.example, .gitignore, .gitattributes
```

## 6. Installation

```bash
git clone https://github.com/radwaelashry30-crypto/baseera-marketplace-analytics.git
cd baseera-marketplace-analytics
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The delivered repository already includes `data/interim/reviews_translated.csv` and
`data/processed/*.parquet`, so the API and frontend work out of the box without
placing raw CSVs — see [`data/README.md`](data/README.md) if you want to rebuild from
raw source.

## 7. Running the notebook (local & Colab)

**Google Colab**: open `notebooks/Baseera_Main_Notebook_Final.ipynb` directly from
this repository on GitHub, or upload it, then **Runtime → Run all**. A dependency
bootstrap checks package versions before anything else runs and, on first use, may
install a compatible numpy/pandas/pyarrow and request one runtime restart — this is
expected, see [`docs/notebook/NOTEBOOK_RUN_GUIDE.md`](docs/notebook/NOTEBOOK_RUN_GUIDE.md).

**Local**: `pip install -r requirements-notebook.txt --extra-index-url https://download.pytorch.org/whl/cpu`,
register a Jupyter kernel, then `jupyter notebook notebooks/Baseera_Main_Notebook_Final.ipynb`.
Full step-by-step instructions, Kaggle authentication, and troubleshooting:
[`docs/notebook/NOTEBOOK_RUN_GUIDE.md`](docs/notebook/NOTEBOOK_RUN_GUIDE.md). Independent
validation evidence (dependency resolution, 5/5 clean stability runs, export/artefact
integrity checks): [`docs/notebook/NOTEBOOK_VALIDATION_REPORT.md`](docs/notebook/NOTEBOOK_VALIDATION_REPORT.md).

## 8. Backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Layered design: `api/v1/endpoints` (HTTP) → `services` (business logic) →
`ml` (pure ML/data code) + `repositories` (cached/optional-DB-backed data access).
`ModelRegistry` loads every optional artefact once at startup and never reloads
per request. Endpoints (health, models, sentiment predict/batch, analytics,
customers, sellers, products, geography, segmentation): full detail in
[`docs/architecture/API_DOCUMENTATION.md`](docs/architecture/API_DOCUMENTATION.md).
Optional relational persistence (sentiment history, feedback, batch-upload records)
via SQLAlchemy + Alembic — opt-in, set `DATABASE_URL`; see
[`docs/architecture/DATABASE_SETUP.md`](docs/architecture/DATABASE_SETUP.md).

## 9. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Vite + React + TypeScript + React Router. `src/api/` centralises HTTP calls;
`src/types/` mirrors the backend's Pydantic schemas field-for-field (the TypeScript
side of `shared/api_contract.json`); `src/pages/`/`src/components/` are pure
presentation. Full detail:
[`docs/architecture/FRONTEND_INTEGRATION.md`](docs/architecture/FRONTEND_INTEGRATION.md).

## 10. Full application launch

```bash
# Windows
run_project.bat
# macOS / Linux
./run_project.sh
```

Both scripts resolve the repository root relative to their own location, create
`.env`/`frontend/.env` from the committed `.example` files if missing, check that
model weights and `frontend/node_modules` are present, then start the backend and
frontend together and open the dashboard. Docker, as an alternative:

```bash
docker compose build && docker compose up   # docker compose down to stop
```

## 11. Smoke-test mode

`notebooks/Baseera_Main_Notebook_Final.ipynb` has an optional
`BASEERA_SMOKE_TEST` flag (Section 0.7, default `False`) that runs the complete
pipeline at a tiny scale (subsampled data, 1 epoch per model) purely to verify
every stage connects end-to-end — data loading, cleaning, feature engineering,
model construction, training, evaluation, artefact save/load, and inference on a
real, programmatically-selected Olist review — writing everything to isolated
`*/smoke_test/` subfolders so it can never overwrite real trained models or
reported metrics. Verified: 5/5 independent fresh-process runs completed with zero
failures. See [`docs/notebook/NOTEBOOK_RUN_GUIDE.md`](docs/notebook/NOTEBOOK_RUN_GUIDE.md#smoke-test-mode-baseera_smoke_test).

## 12. Models and artefacts

See [`models/README.md`](models/README.md) and [`artifacts/README.md`](artifacts/README.md)
for exactly what's shipped, how each file was produced, and how to regenerate or
retrain if a file is missing. Both `bert_review_sentiment/model.safetensors` (638MB)
and `cnn2d_review_sentiment.pt` are tracked via **Git LFS** — run `git lfs install`
before cloning if you don't already have LFS configured.

## 13. Environment variables

See [`.env.example`](.env.example) for the full, documented list (app metadata, CORS
origins, `ENABLE_BERT`/`ENABLE_CNN2D`/`ENABLE_TRANSLATION` feature flags,
`MAX_REVIEW_LENGTH`/`MAX_BATCH_SIZE`, `REQUIRE_API_KEY`/`API_KEYS`,
`TRUSTED_PROXY_HOPS`, optional `DATABASE_URL`). Never commit a populated `.env` —
only `.env.example` with placeholders is tracked.

## 14. Testing

```bash
cd backend && pytest -q          # application test suite (skips cleanly if artefacts are absent)
cd ../frontend && npm run typecheck && npm run test -- --run && npm run build
cd .. && pytest -q               # repository-level structural tests (tests/)
```

## 15. Deployment

Backend: Render (Docker runtime, CPU-only PyTorch wheel, multi-stage `backend/Dockerfile`).
Frontend: Vercel (static build, `frontend/vercel.json`). CI
(`.github/workflows/ci.yml`) runs backend tests, frontend typecheck/test/build, and a
real Docker build-and-boot-and-health-check job on every push/PR. Full detail:
[`docs/architecture/DEPLOYMENT.md`](docs/architecture/DEPLOYMENT.md).

## 16. Academic documentation

[`docs/academic/PROJECT_JOURNEY.md`](docs/academic/PROJECT_JOURNEY.md) /
[`.pdf`](docs/academic/PROJECT_JOURNEY.pdf) — chronological record of every phase,
problem found, and fix applied and verified. [`docs/academic/MODEL_CARD.md`](docs/academic/MODEL_CARD.md) —
model architecture, training configuration, and evaluation methodology.
[`reports/executive_analytics_report.md`](reports/executive_analytics_report.md) —
business-facing summary.

## 17. Presentation

No presentation file is currently tracked in this repository. If one exists outside
version control, add it under `presentation/` and link it here.

## 18. Limitations

- Sentiment predictions are probabilistic estimates from a specific dataset and time period — not ground truth about customer intent.
- The dataset covers January 2017 – August 2018 Brazilian e-commerce only; findings may not generalise to other markets or periods.
- ABSA's aspect-presence gate and underlying sentiment model (CNN2D) are both validated on Olist data individually, but clause-level sentiment as a stand-in for aspect-level sentiment is a heuristic approximation, not independently benchmarked as such.
- Olist's seller/customer base is concentrated in Southeast Brazil; delivery/logistics findings for North/Northeast states rest on comparatively fewer orders.
- Reviews were machine-translated (MarianMT, `opus-mt-ROMANCE-en`) from Portuguese for some pipeline stages; translation errors can shift sentiment-bearing words.

## 19. Responsible AI

Do not use sentiment predictions to make consequential decisions about individual
customers or sellers (e.g. account suspension) without human review. Do not present
the ABSA module's output as validated ground truth. This platform is a demonstration
built on public research data, not a production customer-management system.

## 20. Licence

**Code**: no licence file is currently included in this repository — the repository
owner should add one (e.g. MIT) before any public or academic submission that
requires it. **Dataset**: the Olist data is CC BY-NC-SA 4.0 (Kaggle) — non-commercial,
share-alike, attribution required; this project's derived models and datasets
inherit that restriction.

## 21. Contributors

Add contributor and supervisor names here before submission.

---

*Large binaries note*: `models/bert_review_sentiment/model.safetensors` exceeds
GitHub's 100MB soft limit and is tracked via Git LFS (`git lfs install` before
cloning) — see `.gitattributes`.
