"""Table-by-table cleaning, extracted from notebook section 2 (cells 28-45).

Cleaning happens before merging so each fix is traceable to its source table,
matching the original notebook's approach. Imputation choices are documented
inline and mirror the notebook's own rationale (see DATA_QUALITY_AUDIT.md for
the full justification table).
"""
from __future__ import annotations

import pandas as pd

from .utils import BRAZIL_STATE_NAMES, optimize_dtypes

ORDERS_DATE_COLS = [
    "order_purchase_timestamp", "order_approved_at",
    "order_delivered_carrier_date", "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
REVIEWS_DATE_COLS = ["review_creation_date", "review_answer_timestamp"]
PRODUCT_NUMERIC_COLS = [
    "product_name_lenght", "product_description_lenght", "product_photos_qty",
    "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
]


def assess_duplicates(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Count exact duplicate rows per table (notebook cell 28, assessment half)."""
    return {name: int(df.duplicated().sum()) for name, df in tables.items()}


def drop_duplicate_rows(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Drop exact duplicate rows per table. Notebook cell 28.

    The only table with duplicates in the source data is `geolocation`
    (~261,831 duplicate rows out of ~1M — the same zip-prefix logged with
    micro-differences in coordinates from repeated deliveries).
    """
    cleaned = {}
    for name, df in tables.items():
        before = len(df)
        d = df.drop_duplicates().reset_index(drop=True)
        if len(d) != before:
            pass  # count is reported by assess_duplicates(); avoid duplicate logging here
        cleaned[name] = d
    return cleaned


def assess_missing_values(tables: dict[str, pd.DataFrame]) -> dict[str, dict[str, int]]:
    """Per-table, per-column missing-value counts (notebook cell 30)."""
    report = {}
    for name, df in tables.items():
        nulls = df.isnull().sum()
        report[name] = {col: int(n) for col, n in nulls[nulls > 0].items()}
    return report


def clean_products(products: pd.DataFrame) -> pd.DataFrame:
    """Fill missing category with 'unknown', missing physical specs with 0.

    Justification (notebook §2.3): category is truly unknown for ~610 rows but
    the row still represents a real sale, so it isn't dropped. Physical specs
    (weight/dimensions/photo count) are missing only for a handful of products;
    filling with 0 keeps the dtype numeric without fabricating a plausible value.
    """
    products = products.copy()
    products["product_category_name"] = products["product_category_name"].fillna("unknown")
    for col in PRODUCT_NUMERIC_COLS:
        products[col] = products[col].fillna(0)
    return products


def clean_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    """Fill missing review title/message with sentinel text (notebook §2.3).

    A missing `review_comment_message` means the customer rated with stars but
    chose not to write text — that's valid behavior, not missing data, so it is
    NOT dropped. The sentinel 'No Message' is later used as an explicit filter
    when building the sentiment dataset (see preprocessing.build_sentiment_dataframe).
    """
    reviews = reviews.copy()
    reviews["review_comment_title"] = reviews["review_comment_title"].fillna("No Title")
    reviews["review_comment_message"] = reviews["review_comment_message"].fillna("No Message")
    return reviews


def correct_dtypes(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Parse date columns and correct product length/description dtypes (notebook §2.4)."""
    tables = dict(tables)
    orders = tables["orders"].copy()
    for col in ORDERS_DATE_COLS:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")
    tables["orders"] = orders

    reviews = tables["reviews"].copy()
    for col in REVIEWS_DATE_COLS:
        reviews[col] = pd.to_datetime(reviews[col], errors="coerce")
    tables["reviews"] = reviews

    items = tables["items"].copy()
    items["shipping_limit_date"] = pd.to_datetime(items["shipping_limit_date"], errors="coerce")
    tables["items"] = items

    products = tables["products"].copy()
    for col in ["product_name_lenght", "product_description_lenght", "product_photos_qty"]:
        products[col] = products[col].astype("int64")
    tables["products"] = products

    return tables


def optimize_memory(tables: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, tuple[float, float]]]:
    """Downcast float64/int64 columns per table (notebook §2.5). Returns (tables, before/after MB)."""
    optimized = {}
    report = {}
    for name in ["customers", "items", "payments", "reviews", "orders", "products", "sellers"]:
        if name not in tables:
            continue
        d, before, after = optimize_dtypes(tables[name].copy())
        optimized[name] = d
        report[name] = (before, after)
    for name, df in tables.items():
        optimized.setdefault(name, df)
    return optimized, report


def compress_geolocation(geolocation: pd.DataFrame) -> pd.DataFrame:
    """Collapse geolocation to one row per zip prefix using mean lat/lng (notebook §2.6)."""
    geo_cleaned = (
        geolocation.groupby("geolocation_zip_code_prefix")
        .agg({
            "geolocation_lat": "mean",
            "geolocation_lng": "mean",
            "geolocation_city": "first",
            "geolocation_state": "first",
        })
        .reset_index()
        .rename(columns={
            "geolocation_zip_code_prefix": "zip_code_prefix",
            "geolocation_lat": "lat",
            "geolocation_lng": "lng",
            "geolocation_city": "city",
            "geolocation_state": "state",
        })
    )
    return geo_cleaned


def standardize_state_codes(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Map 2-letter Brazilian state codes to full names in-place on a copy.

    Uses the single canonical mapping in `utils.BRAZIL_STATE_NAMES` everywhere
    state codes are touched, avoiding the notebook's original bug where
    `customer_state` had been remapped to full names while a separately
    computed `state_coords` table still held 2-letter codes, causing every
    lat/lng join to silently return NaN (see notebook cell 80's inline bug-fix
    note). All state-standardization in this project goes through this
    function or `feature_engineering.attach_macro_region`.
    """
    out = df.copy()
    out[column] = out[column].replace(BRAZIL_STATE_NAMES)
    return out
