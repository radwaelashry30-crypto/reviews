"""Raw Olist CSV discovery and loading.

Extracted from notebook cells 9 (`resolve_dataset_path`) and 17 (the manual
9-CSV load). The original notebook had a machine-specific hard-coded
`MANUAL_BASE_PATH` pointing at a folder on the source machine (see
docs/architecture/ARTIFACT_AUDIT.md §7 for the historical record).

That path does not exist in this environment and is intentionally NOT
reproduced here. `resolve_dataset_path` instead checks (in order): an
explicit argument, the `OLIST_DATA_DIR` environment variable, a Kaggle input
directory, and a local `data/raw` directory relative to the project.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REQUIRED_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]

MARKER_FILE = "olist_orders_dataset.csv"


def resolve_dataset_path(manual_path: str | Path | None = None) -> Path:
    """Resolve the folder containing the 9 raw Olist CSVs.

    Priority: 1) `manual_path` if given, 2) `OLIST_DATA_DIR` env var,
    3) a Kaggle input folder, 4) `<project_root>/data/raw`.
    """
    candidates: list[Path] = []
    if manual_path:
        candidates.append(Path(manual_path))
    env_path = os.environ.get("OLIST_DATA_DIR")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path("/kaggle/input/olist-brazilian-ecommerce"))
    candidates.append(Path(__file__).resolve().parents[3] / "data" / "raw")

    for candidate in candidates:
        if (candidate / MARKER_FILE).is_file():
            return candidate

    raise FileNotFoundError(
        "Could not locate the 9 raw Olist CSVs. Place them under data/raw/, "
        "set OLIST_DATA_DIR, or pass an explicit path to resolve_dataset_path()."
    )


def discover_olist_files(base_path: str | Path) -> dict[str, Path]:
    """Return {expected_filename: resolved_path} for every required file found."""
    base_path = Path(base_path)
    found = {}
    for name in REQUIRED_FILES:
        candidate = base_path / name
        if candidate.is_file():
            found[name] = candidate
    return found


@dataclass
class SchemaValidationResult:
    table: str
    ok: bool
    missing_columns: list[str] = field(default_factory=list)
    row_count: int = 0


EXPECTED_SCHEMAS: dict[str, list[str]] = {
    "olist_customers_dataset.csv": [
        "customer_id", "customer_unique_id", "customer_zip_code_prefix",
        "customer_city", "customer_state",
    ],
    "olist_geolocation_dataset.csv": [
        "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
        "geolocation_city", "geolocation_state",
    ],
    "olist_order_items_dataset.csv": [
        "order_id", "order_item_id", "product_id", "seller_id",
        "shipping_limit_date", "price", "freight_value",
    ],
    "olist_order_payments_dataset.csv": [
        "order_id", "payment_sequential", "payment_type",
        "payment_installments", "payment_value",
    ],
    "olist_order_reviews_dataset.csv": [
        "review_id", "order_id", "review_score", "review_comment_title",
        "review_comment_message", "review_creation_date", "review_answer_timestamp",
    ],
    "olist_orders_dataset.csv": [
        "order_id", "customer_id", "order_status", "order_purchase_timestamp",
        "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ],
    "olist_products_dataset.csv": [
        "product_id", "product_category_name", "product_name_lenght",
        "product_description_lenght", "product_photos_qty", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm",
    ],
    "olist_sellers_dataset.csv": [
        "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state",
    ],
    "product_category_name_translation.csv": [
        "product_category_name", "product_category_name_english",
    ],
}


def validate_olist_schema(base_path: str | Path) -> list[SchemaValidationResult]:
    """Check every required CSV exists and has the expected columns."""
    base_path = Path(base_path)
    results = []
    for name, expected_cols in EXPECTED_SCHEMAS.items():
        path = base_path / name
        if not path.is_file():
            results.append(SchemaValidationResult(table=name, ok=False, missing_columns=expected_cols))
            continue
        header = pd.read_csv(path, nrows=0).columns.tolist()
        missing = [c for c in expected_cols if c not in header]
        row_count = sum(1 for _ in open(path, encoding="utf-8")) - 1
        results.append(SchemaValidationResult(table=name, ok=not missing, missing_columns=missing, row_count=row_count))
    return results


def load_customers(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "olist_customers_dataset.csv")


def load_geolocation(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "olist_geolocation_dataset.csv")


def load_order_items(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "olist_order_items_dataset.csv")


def load_payments(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "olist_order_payments_dataset.csv")


def load_reviews(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "olist_order_reviews_dataset.csv")


def load_orders(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "olist_orders_dataset.csv")


def load_products(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "olist_products_dataset.csv")


def load_sellers(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "olist_sellers_dataset.csv")


def load_category_translation(base_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(base_path) / "product_category_name_translation.csv")


def load_all_olist_tables(base_path: str | Path) -> dict[str, pd.DataFrame]:
    """Load all 9 raw tables. Raises FileNotFoundError if any required file is missing."""
    base_path = Path(base_path)
    missing = [f for f in REQUIRED_FILES if not (base_path / f).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required Olist CSVs under {base_path}: {missing}")
    return {
        "customers": load_customers(base_path),
        "geolocation": load_geolocation(base_path),
        "items": load_order_items(base_path),
        "payments": load_payments(base_path),
        "reviews": load_reviews(base_path),
        "orders": load_orders(base_path),
        "products": load_products(base_path),
        "sellers": load_sellers(base_path),
        "translation": load_category_translation(base_path),
    }
