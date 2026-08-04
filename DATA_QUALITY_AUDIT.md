# Data Quality Audit

Source: `olist_full_eda_preprocessing_PYTORCH.ipynb` cells 28–45 (executed output, captured verbatim), cross-checked against `output/olist_cleaned_dataset.parquet`. Machine-readable version: `results/data_quality_summary.json`.

## 1. Duplicate rows

| Table | Duplicates removed |
|---|---|
| customers | 0 |
| geolocation | **261,831** (of ~1,000,163 rows — see below) |
| items | 0 |
| payments | 0 |
| reviews | 0 (exact full-row duplicates only — see finding below) |
| orders | 0 |
| products | 0 |
| sellers | 0 |
| translation | 0 |

**Additional finding, not caught by the notebook's exact-row duplicate check**: `olist_order_reviews_dataset.csv` contains **827 rows with a duplicate `review_id`** (verified directly on the raw file), e.g. a resent review survey landing as a second record with the same id but different other columns — so it's invisible to a byte-for-byte `.duplicated()` check. This project's `feature_engineering.build_reviews_enriched()` deduplicates on `review_id` (keep first) before treating the table as one-row-per-review. See `DATA_GRAIN_AUDIT.md` §6.

## 2. Missing values — before treatment

| Table | Column | Missing |
|---|---|---|
| reviews | review_comment_title | 88,289 |
| reviews | review_comment_message | 58,275 |
| orders | order_approved_at | 160 |
| orders | order_delivered_carrier_date | 1,783 |
| orders | order_delivered_customer_date | 2,965 |
| products | product_category_name | 610 |
| products | product_name_lenght / description_lenght / photos_qty | 610 each |
| products | weight_g / length_cm / height_cm / width_cm | 2 each |

## 3. Imputation decisions and audit verdict

| Table | Column(s) | Decision | Justification | Audit verdict |
|---|---|---|---|---|
| orders | approved_at, delivered_carrier_date, delivered_customer_date | Keep as `NaT` | Canceled/unavailable orders genuinely never reached that stage | **Valid.** Fabricating a date would corrupt every delivery-time KPI. This project's `feature_engineering.add_order_level_features` preserves this. |
| products | product_category_name | Fill `'unknown'` | Category unknown but the sale is real | **Valid.** |
| products | size/weight/photo columns | Fill `0` | Missing for a handful of products only | **Valid but flagged**: a `0` weight/dimension is not physically meaningful if ever used in a downstream shipping-cost model — acceptable for the current EDA scope. |
| reviews | comment_title / comment_message | Fill `'No Title'` / `'No Message'` | Customer rated with stars but chose not to write text | **Valid, and load-bearing**: `'No Message'` becomes an explicit exclusion filter in `preprocessing.build_sentiment_dataframe` — the sentiment task correctly never sees these rows. |
| merged_df | product_id | Drop row (775 rows) | Order-items join failed | **Valid** — nothing to analyze at item level without a product. |
| merged_df | review_score | Fill `0` | No review submitted | **Valid, WITH A HARD GUARDRAIL**: a `0` here is a sentinel for "no review," never a genuine 1–5 rating. Verified: `preprocessing.build_sentiment_dataframe` filters on `review_score.isin([1,2,4,5])`, which structurally excludes score-0 rows from the sentiment task. This guardrail is enforced by `test_preprocessing.py::test_label_mapping_correct`. |
| merged_df | total_payment_value | Fill `price + freight_value` (3 rows) | Payment record missing for 3 orders | **Valid only as a single-item-order proxy** — flagged in `results/data_quality_summary.json` as a documented approximation affecting 3 rows total (negligible at n=98,666 orders), not a general rule. |
| merged_df | main_payment_type | Fill `'not_defined'` (3 rows) | No payment record | **Valid.** |
| merged_df | payment_installments | Fill `1` (3 rows) | No payment record; 1 is the modal case | **Valid.** |

## 4. Data-type corrections

All order/review timestamp columns parsed via `pd.to_datetime(errors="coerce")`; `product_name_lenght`/`description_lenght`/`photos_qty` cast to `int64` after the `0`-fill above.

## 5. Memory optimization

Downcasting `float64`→smallest safe float, `int64`→smallest safe int across customers/items/payments/reviews/orders/products/sellers: **68.15 MB → 62.57 MB (8.2% reduction)**.

## 6. Geolocation compression

`geolocation` (1,000,163 raw rows, 261,831 of them exact duplicates) is compressed by `groupby(zip_code_prefix).agg(mean lat/lng, first city/state)`: **738,332 → 19,015 rows (97.4% reduction)**, computed over the deduplicated 738,332-row table.

## 7. Post-cleaning validation

- `product_id` drop: 775 rows removed at merge time (order-items join failures).
- Remaining post-fix missing values: `order_approved_at` (15), `order_delivered_carrier_date` (1,194), `order_delivered_customer_date` (2,454) — all genuine, deliberately un-imputed NaT values for canceled/unavailable/in-transit orders.
- Price outliers: 8,427 rows (7.5% of item-level data) flagged via IQR (1.5×) on `price` — **flagged, never removed**, preserved as `is_price_outlier` for transparency in downstream analysis.

## 8. State-code standardization

The notebook maps 2-letter Brazilian state codes (`SP`, `RJ`, ...) to full names (`São Paulo`, `Rio de Janeiro`, ...) for `customers` and `sellers`, but the raw `geolocation` table's `state` column is never remapped in the same pass — a documented bug the notebook itself flags and fixes ad hoc in cell 80 ("BUG FIX" comment) by remapping `state_coords["state"]` immediately before the affected map join. This project centralizes that mapping in `utils.state_code_to_name` / `cleaning.standardize_state_codes`, applied consistently everywhere a state code is touched, so the bug class cannot recur.
