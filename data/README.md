# Data Directory

## Layout

```
data/
├── raw/         # place the 9 raw Olist CSVs here (not included — see below)
├── interim/     # reviews_translated.csv (translation cache/checkpoint) — INCLUDED
└── processed/   # canonical enriched Parquet datasets — INCLUDED
```

## Required raw filenames (place under `data/raw/`)

```
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_orders_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

Expected schemas are validated by `backend/app/ml/data_loading.py::validate_olist_schema()`. Source: [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle, CC BY-NC-SA 4.0 — see the dataset's own license before redistribution).

## Data provenance

The raw 9 CSVs were not present in the originally uploaded project folder (`update-20260731T143927Z-1-001/update`) — only its derived outputs were. They were subsequently located in a separate, machine-local `E-commerce/Dataset/` folder (the exact relative location the notebook's own hard-coded `MANUAL_BASE_PATH` pointed to — path redacted here, see `docs/architecture/ARTIFACT_AUDIT.md` §7) and are included in this delivery under `data/raw/`. `data/processed/*.parquet` in this delivery was regenerated for real from these raw CSVs via `run_pipeline.py --clean` (not derived from the notebook's own export) — see `docs/architecture/DATA_GRAIN_AUDIT.md` for what changed as a result.

This project also ships:
- `data/interim/reviews_translated.csv` — 100,000 reviews with English translations (41,723 non-empty), the genuine output of the notebook's translation step.

## Raw/interim/processed separation

- **raw**: untouched CSVs as downloaded, never committed to git (see `.gitignore`).
- **interim**: intermediate artifacts that are expensive to regenerate (translation), safe to cache and reuse.
- **processed**: final, analysis-ready tables at their documented grain, safe to load directly by the backend.

## Rebuilding from source

```bash
# 1. Place the 9 raw CSVs under data/raw/
# 2. Clean + build canonical enriched datasets:
python backend/scripts/run_pipeline.py --data-dir data/raw --clean

# 3. (Optional, slow, downloads a ~300MB translation model) Translate reviews:
python backend/scripts/translate_reviews.py --input data/raw/olist_order_reviews_dataset.csv --allow-external-downloads

# 4. Rebuild cleaned CSV/Parquet + EDA + segmentation:
python backend/scripts/run_pipeline.py --data-dir data/raw --clean --eda --segment
```

## Redistribution

The raw Olist dataset is licensed CC BY-NC-SA 4.0 by Olist/Kaggle — non-commercial use, share-alike, attribution required. Do not redistribute the raw CSVs as part of a commercial product; this project's derived enriched datasets and trained models inherit the same restriction.
