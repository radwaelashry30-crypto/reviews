"""Data access for analytics: reads precomputed result JSON files and processed
Parquet tables from disk. Loaded once at startup and cached on `app.state`;
never re-reads the full raw dataset per request.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.core.config import settings


class AnalyticsRepository:
    def __init__(self) -> None:
        self._json_cache: dict[str, dict] = {}
        self._df_cache: dict[str, pd.DataFrame] = {}

    def load_all(self) -> None:
        for name in [
            "business_kpis", "monthly_orders", "monthly_revenue", "review_distribution",
            "delivery_summary", "payment_distribution", "state_performance",
            "category_performance", "rfm_segments", "repeat_purchase_rate",
            "late_delivery_significance_test",
        ]:
            path = settings.RESULTS_DIR / f"{name}.json"
            if path.is_file():
                with open(path, encoding="utf-8") as f:
                    self._json_cache[name] = json.load(f)

        # Only load the columns the live API actually reads (see
        # analytics_service.py) -- and only the 3 of 5 canonical datasets it
        # touches at all. order_items_enriched/reviews_enriched are used by
        # offline scripts (run_eda.py, run_pipeline.py) but never by any API
        # endpoint, so keeping them out of long-lived process memory matters
        # on RAM-constrained hosts (verified: this cut the free-tier
        # deployment under its 512MB limit). Full row-level tables remain
        # available locally/via Docker for anyone running the pipeline.
        column_allowlist: dict[str, list[str] | None] = {
            "orders_enriched": ["order_id", "customer_city"],
            "customers_enriched": ["customer_unique_id", "is_repeat_customer", "order_count", "total_spend"],
            "sellers_enriched": ["seller_id", "late_delivery_rate", "item_revenue", "order_count"],
        }
        for name, columns in column_allowlist.items():
            path = settings.PROCESSED_DATA_DIR / f"{name}.parquet"
            if path.is_file():
                self._df_cache[name] = pd.read_parquet(path, columns=columns)

    def get_json(self, name: str) -> dict | None:
        return self._json_cache.get(name)

    def get_dataframe(self, name: str) -> pd.DataFrame | None:
        return self._df_cache.get(name)

    def is_ready(self) -> bool:
        return bool(self._json_cache) or bool(self._df_cache)

    def available_datasets(self) -> list[str]:
        return list(self._df_cache.keys())

    def available_results(self) -> list[str]:
        return list(self._json_cache.keys())
