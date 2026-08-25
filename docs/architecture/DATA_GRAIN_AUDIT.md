# Data Grain Audit

## 1. The problem

The notebook (cells 42–47) builds a single merged dataframe:

```
orders -> customers -> items -> products(+translation) -> sellers -> payment_summary -> payment_type -> installments -> review_summary
```

`payments` and `reviews` ARE aggregated to one row per order before the merge (`payments_summary`, `payment_type_mode`, `installments_summary`, `reviews_summary` — all `groupby("order_id")`), which is correct. But the merge to `items` is one-to-many: an order with N items produces N rows, and every order-level column (`total_payment_value`, `order_status`, `review_score`, `customer_*`, dates, ...) is repeated N times.

**Verified on this project's actual data** (`output/olist_cleaned_dataset_legacy_order_item_merged.parquet`, reproducing the notebook's own merge):

| | Value |
|---|---|
| Merged dataframe rows (order-item grain) | 112,650 |
| Unique `order_id` | 98,666 |
| Row-count inflation | **14.17%** |

Several notebook EDA cells compute KPIs directly from this order-item-grain `df` using `.size()` or `.value_counts()`, which counts ROWS, not unique orders:

| Notebook cell | KPI | Computation used | Risk |
|---|---|---|---|
| 52 | Order-status distribution | `px.pie(df, names="order_status")` | Counts item rows — verified: "delivered" reads as 110,197 at item grain vs. 96,478 unique orders (+14.2%) |
| 55 | Monthly orders trend | `df.groupby("order_year_month").size()` | Same inflation, unevenly distributed by month (multi-item orders aren't uniform across time) |
| 58 | Top cities by orders | `df["customer_city"].value_counts()` | Counts item rows per city, not orders per city |
| 83 | Payment-method distribution | `px.pie(df, names="main_payment_type")` | Counts item rows, not orders |
| 98 / 101 | Late-delivery % by state / by seller | `pivot_table(..., values="order_id", aggfunc="count")` | Counts item rows in the pivot, not unique orders |
| 110 (RFM) | `Frequency=("order_id","nunique")` | **Correct** (uses `nunique`, not `count`) | None — this one was already right |
| 110 (RFM) | `Monetary=("total_payment_value","sum")` | Sums a value that is REPEATED once per item | An order with 3 items contributes 3x its true payment total to that customer's Monetary score |

`total_payment_value` and `review_score` are correct AT THE ORDER LEVEL (aggregated once before merging), but because they're then repeated across N item rows, any `.sum()` or `.mean()` computed over the item-grain frame double(or N-times)-counts them. The RFM Monetary calculation is the clearest concrete instance of this: it sums `total_payment_value` grouped by customer over the item-grain `df`, which inflates Monetary for every customer whose orders contain more than one item.

## 2. Canonical grain-correct datasets (this project)

Implemented in `backend/app/ml/feature_engineering.py`:

| Dataset | Grain | Row count (this project's data) | Use for |
|---|---|---|---|
| `orders_enriched` | one row per `order_id` | **99,441** (all raw orders — see §5 for why this is MORE complete than the legacy path's 98,666) | order counts, monthly trend, revenue (payment-based), delivery performance, late-delivery rate, RFM Frequency/Monetary |
| `order_items_enriched` | one row per order item | 112,650 | category revenue (sum of item `price`), item-level freight analysis |
| `reviews_enriched` | one row per `review_id` | 99,173 (deduplicated from the raw 100,000-row/827-duplicate reviews table — see §6) | review-score distribution, review text analysis |
| `customers_enriched` | one row per `customer_unique_id` | 96,096 | repeat-purchase rate, customer segmentation |
| `sellers_enriched` | one row per `seller_id` | 3,095 | seller late-delivery ranking, seller item revenue |
| `legacy_order_item_merged` | order-item grain (notebook reproduction) | 112,650 | reproducing the notebook's ORIGINAL numbers only — never used for order-level KPIs in this project's services/API |

Every join is validated with `feature_engineering.check_join_cardinality()`, which reports one-to-one / one-to-many / many-to-many and the duplicate-key counts on each side, so an accidental many-to-many merge cannot pass silently (`test_data_grain.py::test_check_join_cardinality_detects_one_to_many`).

## 3. Corrected calculations vs. notebook

| KPI | Notebook (order-item grain) | Corrected (order grain) | Difference |
|---|---|---|---|
| "delivered" order-status count | 110,197 | 96,478 | -12.4% (over-count removed) |
| Total unique orders | not computed directly; `len(df)`=112,650 implied | **99,441** (`orders_enriched`, includes orders with no item row) | -12.6%, AND +775 orders recovered vs. the item-joined path's 98,666 (see §5) |
| "unavailable" order-status count | 6 (item-joined path) | **609** (`orders_enriched`) | +603 — see §5, this is not noise |
| RFM Monetary | sum of repeated per-item payment values | sum of one payment value per order | see `results/rfm_segments.json` — computed correctly in this project from the start |

`results/business_kpis.json`, `results/monthly_orders.json`, `results/state_performance.json`, and `results/rfm_segments.json` in this project are all computed from `orders_enriched`/`customers_enriched`, i.e. already corrected — they were never computed the inflated way and then "fixed", so there is no separate before/after file for them; this document is the record of what would have been wrong had the notebook's row-count approach been reused.

## 4. Data provenance note

The raw 9 Olist CSVs were not present in the originally uploaded `update/` folder, but were subsequently located in a separate, machine-local `E-commerce/Dataset/` folder — the exact relative location the notebook's own `MANUAL_BASE_PATH` hard-coded (path redacted; see `docs/architecture/ARTIFACT_AUDIT.md` §7). They are included in this delivery under `data/raw/`, and `data/processed/*.parquet` was regenerated for real from them via `run_pipeline.py --data-dir data/raw --clean` (using `data_loading.py` + `feature_engineering.py`'s raw-table functions directly — not derived from the notebook's own export).

## 5. A second, more complete finding from running on genuine raw source

Building `orders_enriched` directly from `orders`+`customers`+`payments`+`reviews` (this project's function) rather than from the notebook's own `legacy_order_item_merged` export produces a materially different, MORE COMPLETE order count:

| Source | Unique orders | canceled | unavailable |
|---|---|---|---|
| `legacy_order_item_merged` (drops rows with no matching `order_items` row, per notebook's `dropna(subset=["product_id"])`) | 98,666 | 461 | 6 |
| `orders_enriched` (built directly from `orders`, independent of the `items` join) | **99,441** | **625** | **609** |

**775 orders have no matching `order_items` row at all**, and those missing orders are disproportionately `canceled`/`unavailable` (an order that was canceled or never became available to ship often never had an item allocated to it). The notebook's own merge silently drops these 775 orders via `dropna(subset=["product_id"])` — which means **the notebook's `unavailable`-status count (6) understates the true figure (609) by two orders of magnitude**, purely as an artifact of which table the KPI happened to be computed from, not a genuine finding about the marketplace.

`orders_enriched` (this project's canonical order-grain dataset, and what every order-count/status KPI in `results/business_kpis.json` and the API is computed from) does NOT have this blind spot — it is built without ever joining through `items`, so all 99,441 raw orders are represented regardless of whether they have a matching item row. This was caught by this project's own `assert out["review_id"].is_unique` guard in `build_reviews_enriched` failing on genuine raw data (a separate, related bug — see below) during verification, which prompted re-deriving every canonical dataset from the real raw CSVs instead of the notebook's own already-lossy export.

## 6. Related bug found and fixed: duplicate `review_id` in the raw data

`olist_order_reviews_dataset.csv` genuinely contains **827 duplicate `review_id` rows** out of 100,000 (verified directly: `review_id.duplicated().sum() == 827`; e.g. a resent review survey landing as a second record with the same id). The notebook's own duplicate check (`reviews.duplicated().sum()`) reports 0 because it checks for exact FULL-ROW duplicates, not duplicate `review_id`s with differing other columns — so this was never surfaced by the original notebook. `feature_engineering.build_reviews_enriched()` now deduplicates on `review_id` (keep first) before asserting the one-row-per-review grain, with a regression test (`test_data_grain.py::test_reviews_enriched_deduplicates_genuine_duplicate_review_ids`).
