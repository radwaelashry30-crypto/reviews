#!/usr/bin/env python
"""Run the full EDA suite against the canonical enriched datasets, saving figures + JSON results.

Usage:
    python run_eda.py --processed-dir data/processed --figures-dir figures/eda --results-dir results
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # noqa: E402

from app.ml import eda  # noqa: E402
from app.ml.utils import write_json  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the EDA suite (grain-correct) and save figures + JSON results.")
    parser.add_argument("--processed-dir", default=str(PROJECT_ROOT / "data" / "processed"))
    parser.add_argument("--figures-dir", default=str(PROJECT_ROOT / "figures" / "eda"))
    parser.add_argument("--results-dir", default=str(PROJECT_ROOT / "results"))
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    figures_dir = Path(args.figures_dir)
    results_dir = Path(args.results_dir)

    required = ["orders_enriched.parquet", "order_items_enriched.parquet", "reviews_enriched.parquet", "customers_enriched.parquet"]
    missing = [f for f in required if not (processed_dir / f).is_file()]
    if missing:
        raise SystemExit(f"Missing processed datasets under {processed_dir}: {missing}. Run run_pipeline.py --clean --build-features first.")

    orders = pd.read_parquet(processed_dir / "orders_enriched.parquet")
    items = pd.read_parquet(processed_dir / "order_items_enriched.parquet")
    reviews = pd.read_parquet(processed_dir / "reviews_enriched.parquet")
    customers = pd.read_parquet(processed_dir / "customers_enriched.parquet")
    sellers_path = processed_dir / "sellers_enriched.parquet"
    sellers = pd.read_parquet(sellers_path) if sellers_path.is_file() else None

    if sellers is not None:
        summary = eda.compute_business_summary(orders, items, customers, sellers)
        write_json(results_dir / "business_kpis.json", summary)
        print("Business summary:", summary)

    print("Order status distribution:", eda.order_status_distribution(orders, figures_dir / "order_status.html").to_dict())
    print("Repeat purchase rate:", eda.repeat_purchase_rate(customers))
    print("Delivery summary:", eda.delivery_time_distribution(orders, figures_dir / "delivery_time.html"))
    print("Late delivery significance test:", eda.late_delivery_significance_test(orders))

    eda.monthly_orders_trend(orders, figures_dir / "monthly_orders.html")
    eda.top_cities_by_orders(orders, save_path=figures_dir / "top_cities.html")
    eda.top_categories_by_revenue(items, save_path=figures_dir / "top_categories_revenue.html")
    eda.review_score_distribution(orders, figures_dir / "review_distribution.html")
    eda.peak_shopping_heatmap(orders, figures_dir / "peak_shopping_heatmap.html")
    eda.late_delivery_rate_by_state(orders, save_path=figures_dir / "late_delivery_by_state.html")
    eda.review_score_by_delay_bucket(reviews, figures_dir / "review_score_by_delay_bucket.html")
    eda.payment_method_distribution(orders, figures_dir / "payment_distribution.html")
    eda.monthly_revenue_trend(orders, figures_dir / "monthly_revenue.html")
    eda.spearman_correlation(orders, items, figures_dir / "spearman_correlation.html")

    write_json(results_dir / "late_delivery_significance_test.json", eda.late_delivery_significance_test(orders))
    write_json(results_dir / "repeat_purchase_rate.json", eda.repeat_purchase_rate(customers))
    print(f"\nSaved figures to {figures_dir} and results to {results_dir}")


if __name__ == "__main__":
    main()
