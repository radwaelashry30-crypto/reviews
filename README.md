# Olist Marketplace Analytics and Customer Sentiment Intelligence Platform

End-to-end analytics, data engineering, and review-sentiment intelligence for the Olist Brazilian e-commerce marketplace — a FastAPI backend, a React/TypeScript frontend, and the full ML pipeline extracted and corrected from the original research notebook.

## 1. Overview

This project turns a single 151-cell research notebook into a modular, testable, deployable application with:
- A relational data-engineering pipeline (9 raw tables → grain-correct enriched datasets)
- Business KPI generation and RFM customer segmentation
- Binary review-sentiment classification (BERT and CNN2D, both genuinely trained and verified)
- A FastAPI backend serving all of the above
- A React + TypeScript dashboard/inference frontend
- Full data-leakage, data-grain, and model-comparison audits with corrected numbers

## 2. Business problem

Olist is a Brazilian e-commerce marketplace. This project answers: how is the marketplace performing (orders, revenue, delivery, payments), which customers/sellers/categories need attention, and can a review's text alone flag its sentiment automatically instead of waiting on the star rating?

## 3. Dataset

[Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — 9 relational CSVs: orders, customers, order items, payments, reviews, products, sellers, geolocation, category translation. See `data/README.md` for schemas and placement.

## 4. Relational data model

```
orders --(customer_id)--> customers
orders --(order_id, 1:N)--> order_items --(product_id)--> products --(category)--> translation
order_items --(seller_id)--> sellers
orders --(order_id, aggregated 1:1)--> payments_summary, review_summary
```

## 5. Data-quality process

See `DATA_QUALITY_AUDIT.md`. Highlights: 261,831 duplicate geolocation rows removed; missing delivery dates deliberately kept as `NaT` (never fabricated) for canceled/undelivered orders; missing review text filled with an explicit `'No Message'` sentinel that doubles as the sentiment task's exclusion filter; price outliers flagged (IQR), never silently dropped.

## 6. Data-grain audit (critical)

The notebook's single merged dataframe is at **order-item grain** (112,650 rows, 98,666 unique orders — a 14.2% inflation on any row-count KPI). This project provides grain-correct canonical datasets (`orders_enriched`, `order_items_enriched`, `reviews_enriched`, `customers_enriched`, `sellers_enriched`) and uses the right one for every KPI. Full detail: `DATA_GRAIN_AUDIT.md`.

## 7. Feature engineering

`delivery_days`, `delivery_delay_days`, `is_late_delivery`, `order_hour`/`order_day`/`order_year_month`, `is_price_outlier` (IQR), `customer_order_count`, `seller_late_delivery_rate`, `delay_bucket`. Documented per-grain in `backend/app/ml/feature_engineering.py`.

## 8. EDA

`backend/app/ml/eda.py` / `run_eda.py`: order-status distribution, monthly order/revenue trend, top cities/categories, review-score distribution, peak-hour heatmap, delivery-time distribution and late-delivery rate by state/seller, payment/installment distribution, Spearman correlation, and a Welch's t-test + Mann-Whitney U significance test confirming late delivery significantly lowers review scores (p ≈ 0).

## 9. Customer segmentation

RFM (Recency/Frequency/Monetary) + K-Means (k=4, seed=42, n_init=10), with Frequency/Monetary computed correctly at order grain (not inflated by item count). Segment names (`Champion`/`Loyal Customer`/`Potential Loyal`/`At Risk`) are derived from each cluster's own mean Monetary rank, not hard-coded to a cluster id. See `backend/app/ml/segmentation.py`, `results/rfm_segments.json`.

## 10. Sentiment classification task

Binary: **1-2 stars → Negative (0), 4-5 stars → Positive (1)**. 3-star reviews and reviews with no written text are excluded. Predictions are probabilistic and dataset-dependent, not objective truth.

## 11. BERT model

Fine-tuned from `LiYuan/amazon-review-sentiment-analysis` (`bert-base-multilingual-uncased` architecture — verified NOT DistilBERT), `AutoModelForSequenceClassification`, `num_labels=2`. `max_len=128`, `batch_size=8`, `epochs=3`, `lr=2e-5`, `weight_decay=0.01`, linear warmup (10%) + decay, gradient clipping at 1.0, early stopping (patience 2), seed 42. Artifact: `models/bert_review_sentiment/` (verified genuine `save_pretrained()` output).

## 12. CNN2D model

`CNN2DReviewSentiment` (PyTorch, from scratch): `Embedding(30000,100,pad_idx=0)` → 4 parallel `Conv2D` branches (filter sizes 2/3/4/5, 32 filters each) → `BatchNorm2d` → `ReLU` → adaptive global max-pool → concat → `Dropout(0.5)` → `Linear(128,32)` → `ReLU` → `Dropout(0.5)` → `Linear(32,1)` (raw logit). `SimpleVocabTokenizer` (custom, frequency-capped, 0=pad/1=OOV), `max_len=100`. `batch_size=64`, `epochs=10`, `lr=1e-3`, `weight_decay=1e-3`, label smoothing 0.1, `ReduceLROnPlateau`, early stopping (patience 3), seed 42. **Verified**: `strict=True` state-dict load succeeds, 3,049,345 trainable parameters.

## 13. Notebook-reported metrics (NOT leakage-free — see §15)

| | BERT (n=2,000) | CNN2D (n=7,613) |
|---|---|---|
| Accuracy | 0.9275 | 0.9192 |
| F1 (macro) | 0.9134 | 0.9074 |
| ROC-AUC | 0.9716 | 0.9717 |
| MCC | 0.8270 | 0.8190 |

Stored verbatim in `results/notebook_reported_metrics.json`.

## 14. Reproduced metrics (corrected split, real forward-pass evaluation)

| | BERT (n=6,297) | CNN2D (n=6,297) |
|---|---|---|
| Accuracy | 0.9344 | 0.9222 |
| F1 (macro) | 0.9271 | 0.9159 |
| ROC-AUC | 0.9755 | **0.9770** |
| MCC | 0.8542 | 0.8370 |

Both evaluated on the IDENTICAL corrected/deduplicated test split — see `results/reproduced_metrics.json`, `results/fair_model_comparison.json`.

## 15. Leakage warning

The notebook's original split leaked 1,097 duplicate review texts across train/val/test (verified from its own captured output) and never regenerated `X_train`/`X_val`/`X_test` after deduplicating in a later cell. Full detail and the corrected pipeline: `DATA_LEAKAGE_AUDIT.md`.

## 16. Fair-comparison methodology

The notebook compared BERT on a 2,000-row subsample against CNN2D on the full 7,613-row split — different populations, different sizes. This project's fair-comparison mode evaluates both on the same 6,297-row corrected test set. Full detail: `MODEL_COMPARISON_AUDIT.md`.

## 17. Explainable AI

SHAP `PartitionExplainer` over the fine-tuned BERT pipeline, sample size 8 (configurable), explaining rows drawn from the stored split manifest only. `backend/app/ml/explainability.py`; degrades gracefully (reports `available: false`) if `shap` isn't installed rather than crashing.

## 18. Fake-review module (experimental)

`jb10231/fake-review-detector` over negative reviews. The notebook's own run flagged 0/11,407 as fake — documented in `backend/app/ml/fake_review_detection.py` as **not evidence all reviews are genuine** (likely domain shift / calibration, not a validated fraud signal).

## 19. ABSA module (experimental)

`yangheng/deberta-v3-base-absa-v1.1`, sentiment-given-aspect (not extraction) over {delivery, product quality, price, customer service, packaging}, sample size 200. `backend/app/ml/absa.py`.

## 20. Backend architecture

FastAPI, layered: `api/v1/endpoints` (HTTP) → `services` (business logic, no FastAPI imports) → `ml` (pure ML/data code) + `repositories` (cached data access). `ModelRegistry` loads every optional artifact once at startup (`app/main.py` lifespan) and never reloads per request. See `API_DOCUMENTATION.md`.

## 21. Frontend architecture

Vite + React + TypeScript + React Router. `src/api/` centralizes all HTTP calls; `src/types/` mirrors backend Pydantic schemas field-for-field; `src/hooks/` wraps loading/error state; `src/pages/` + `src/components/` are pure presentation — no ML logic in the frontend. See `FRONTEND_INTEGRATION.md`.

## 22. API endpoints

`/api/v1/health`, `/models/status`, `/models/info`, `/sentiment/predict[-batch]`, `/analytics/summary|orders/monthly|revenue/monthly|reviews/distribution|delivery/summary|payments/distribution`, `/customers/summary|top-cities|segments[/{name}]`, `/sellers/summary|performance`, `/products/categories|category-performance`, `/geography/state-performance`, `/segmentation/rfm-summary`, `/segmentation/predict`. Full detail: `API_DOCUMENTATION.md`.

## 23. Folder structure

```
Olist_Marketplace_Platform/
├── README.md, requirements.txt, .gitignore, .env.example, docker-compose.yml, Makefile
├── ARTIFACT_AUDIT.md, DATA_QUALITY_AUDIT.md, DATA_LEAKAGE_AUDIT.md, DATA_GRAIN_AUDIT.md, MODEL_COMPARISON_AUDIT.md
├── API_DOCUMENTATION.md, FRONTEND_INTEGRATION.md
├── backend/            # FastAPI app + ML code + scripts + tests
├── frontend/            # Vite + React + TS starter
├── shared/               # API contract, label mapping, model manifest, example responses
├── models/                # bert_review_sentiment/, cnn2d_review_sentiment.pt
├── artifacts/              # tokenizers, split manifest, RFM scaler/kmeans, manifests
├── config/                  # project/bert/cnn2d config JSON
├── data/                      # raw/ (empty, see data/README.md), interim/, processed/
├── output/                      # legacy order-item-grain export (notebook reproduction only)
├── results/                      # KPIs, metrics, audits' machine-readable backing data
├── figures/                        # EDA/model/SHAP/segmentation figures
├── notebooks/                       # original notebook (preserved)
├── reports/                          # executive_analytics_report.md
└── original_project_backup/           # everything from the uploaded folder, preserved as-is
```

## 24. Installation

```bash
git clone <this-repo> && cd Olist_Marketplace_Platform
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 25. Data placement

See `data/README.md`. The delivered project already includes `data/interim/reviews_translated.csv` and `data/processed/*.parquet`, so the API and frontend work out of the box without placing raw CSVs.

## 26. Backend startup

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 27. Frontend startup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## 28. Docker startup

```bash
docker compose build
docker compose up
docker compose down
```

## 29. Translation

```bash
python backend/scripts/translate_reviews.py --allow-external-downloads
```
Reuses `data/interim/reviews_translated.csv` if present; only translates rows that don't already have a translation.

## 30. Full pipeline

```bash
python backend/scripts/run_pipeline.py --data-dir data/raw --clean --eda --segment
```

## 31. Training

```bash
python backend/scripts/train.py --model bert --epochs 3 --batch-size 8 --learning-rate 2e-5
python backend/scripts/train.py --model cnn2d --epochs 10 --batch-size 64 --learning-rate 0.001
```

## 32. Evaluation

```bash
python backend/scripts/evaluate.py --model bert --model-path models/bert_review_sentiment --split-manifest artifacts/split_manifest.json
python backend/scripts/evaluate.py --model cnn2d --checkpoint models/cnn2d_review_sentiment.pt --tokenizer artifacts/cnn2d_tokenizer.pkl --split-manifest artifacts/split_manifest.json
```

## 33. Inference

```bash
python backend/scripts/inference.py --text "The product arrived early and works perfectly." --model bert
```

## 34. API examples

See `API_DOCUMENTATION.md` for curl/JS/React examples for every endpoint.

## 35. Testing

```bash
cd backend
pytest -q          # 46 tests, all pass when artifacts are present; artifact-dependent tests skip cleanly otherwise
cd ../frontend
npm run typecheck
npm run build
```

## 36. CPU and GPU notes

Everything runs on CPU (verified: BERT inference ~18ms/review, ~0.35s/batch of 8 on CPU). `get_device()` auto-selects CUDA when available. Install the CUDA build of PyTorch separately (see https://pytorch.org/get-started/locally/) — this project's `requirements.txt` intentionally does not pin a CUDA-specific wheel.

## 37. Reproducibility notes / random seed

Seed **42** everywhere: dataset split, class-weight computation, K-Means, PyTorch/NumPy/Python RNG (`utils.set_seed`). BERT/CNN tokenizers are fit on the TRAIN partition only. The split manifest (`artifacts/split_manifest.json`) stores stable `review_id`/`text_hash` identifiers so evaluation never depends on re-running the split.

## 38. Limitations

- Sentiment predictions are probabilistic estimates from a specific dataset and time period — not ground truth about customer intent.
- The dataset covers Jan 2017–Aug 2018 Brazilian e-commerce only; findings may not generalize to other markets or periods.
- Fake-review and ABSA modules are exploratory, unvalidated for this domain.

## 39. Dataset-bias warning

Olist's seller/customer base is concentrated in Southeast Brazil; delivery/logistics findings for North/Northeast states rest on comparatively fewer orders.

## 40. Translation-quality warning

Reviews were machine-translated (MarianMT, `opus-mt-ROMANCE-en` — see ARTIFACT_AUDIT.md §4) from Portuguese. Translation errors can shift sentiment-bearing words; the CNN/BERT models were trained and evaluated on this translated text, not the original Portuguese.

## 41. Responsible-use statement

Do not use sentiment predictions to make consequential decisions about individual customers or sellers (e.g. account suspension) without human review. Do not present the fake-review or ABSA modules' output as validated ground truth.

## 42. Contributors / Supervisor

Add your name(s) and supervisor here before submission.

## 43. Report

See `reports/executive_analytics_report.md`.

## 44. Git LFS / large files

| Artifact | Size |
|---|---|
| `models/bert_review_sentiment/model.safetensors` | 638.4 MB |
| `models/cnn2d_review_sentiment.pt` | 11.6 MB |
| `artifacts/cnn2d_tokenizer.pkl` | 105 KB |

The BERT weight file exceeds GitHub's 100MB soft limit. Use Git LFS:
```bash
git lfs install
git lfs track "models/bert_review_sentiment/model.safetensors"
git add .gitattributes
```
The file is preserved in this ZIP regardless of Git LFS setup.

## 45. License

Code: add your preferred license (e.g. MIT). Dataset: Olist data is CC BY-NC-SA 4.0 (Kaggle) — non-commercial, share-alike, attribution required; this project's derived models/datasets inherit that restriction.
