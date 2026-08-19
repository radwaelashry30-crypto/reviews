#!/usr/bin/env python
"""Orchestrates the full pipeline from raw CSVs to processed/enriched datasets.

Usage:
    python run_pipeline.py --data-dir data/raw --clean --build-features --eda --segment

Expensive/optional stages are opt-in flags. Training is intentionally NOT a
flag here -- use train.py directly, so it can never be triggered by accident
or from an API endpoint. Translation only re-runs rows missing a translation;
it never re-downloads or re-translates rows that already have one.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # noqa: E402

from app.ml import cleaning, data_loading, feature_engineering as fe, segmentation as seg  # noqa: E402
from app.ml.utils import write_json  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent


def stage_clean_and_build_features(data_dir: Path) -> dict[str, pd.DataFrame]:
    print(f"Loading raw Olist tables from {data_dir} ...")
    tables = data_loading.load_all_olist_tables(data_dir)

    print("Assessing/removing duplicate rows ...")
    dup_report = cleaning.assess_duplicates(tables)
    print(dup_report)
    tables = cleaning.drop_duplicate_rows(tables)

    tables["products"] = cleaning.clean_products(tables["products"])
    tables["reviews"] = cleaning.clean_reviews(tables["reviews"])
    tables = cleaning.correct_dtypes(tables)
    tables, mem_report = cleaning.optimize_memory(tables)
    print("Memory optimization:", mem_report)

    tables["geolocation"] = cleaning.compress_geolocation(tables["geolocation"])
    tables["sellers"] = cleaning.standardize_state_codes(tables["sellers"], "seller_state")
    tables["customers"] = cleaning.standardize_state_codes(tables["customers"], "customer_state")

    print("Building canonical enriched datasets ...")
    orders_enriched = fe.build_orders_enriched(tables["orders"], tables["customers"], tables["payments"], tables["reviews"])
    order_items_enriched = fe.build_order_items_enriched(tables["items"], tables["products"], tables["sellers"], tables["translation"])
    reviews_enriched = fe.build_reviews_enriched(tables["reviews"], orders_enriched)
    customers_enriched = fe.build_customers_enriched(tables["customers"], orders_enriched)
    sellers_enriched = fe.build_sellers_enriched(order_items_enriched, orders_enriched)

    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    orders_enriched.to_parquet(processed_dir / "orders_enriched.parquet", index=False)
    order_items_enriched.to_parquet(processed_dir / "order_items_enriched.parquet", index=False)
    reviews_enriched.to_parquet(processed_dir / "reviews_enriched.parquet", index=False)
    customers_enriched.to_parquet(processed_dir / "customers_enriched.parquet", index=False)
    sellers_enriched.to_parquet(processed_dir / "sellers_enriched.parquet", index=False)
    print(f"Saved 5 canonical datasets to {processed_dir}")

    legacy = fe.build_legacy_merged_dataframe(
        tables["orders"], tables["customers"], tables["items"], tables["products"],
        tables["sellers"], tables["payments"], tables["reviews"], tables["translation"],
    )
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    legacy.to_csv(output_dir / "olist_cleaned_dataset_legacy_order_item_merged.csv", index=False)
    legacy.to_parquet(output_dir / "olist_cleaned_dataset_legacy_order_item_merged.parquet", index=False)

    return {
        "orders_enriched": orders_enriched, "order_items_enriched": order_items_enriched,
        "reviews_enriched": reviews_enriched, "customers_enriched": customers_enriched,
        "sellers_enriched": sellers_enriched,
    }


def stage_segment(orders_enriched: pd.DataFrame) -> None:
    print("Building RFM segmentation ...")
    rfm = seg.build_rfm_table(orders_enriched)
    rfm_scaled, scaler = seg.scale_rfm_features(rfm)

    print("Selecting k via silhouette score (evidence only -- RFM_N_CLUSTERS stays the business-chosen default unless overridden) ...")
    best_k, k_evidence = seg.select_k(rfm_scaled)
    write_json(PROJECT_ROOT / "results" / "rfm_k_selection.json", {
        "selected_by_silhouette": best_k,
        "used_in_production": seg.RFM_N_CLUSTERS,
        "criterion": "max silhouette",
        "evidence": k_evidence,
    })
    print(f"Silhouette-best k={best_k} (evidence in results/rfm_k_selection.json); using RFM_N_CLUSTERS={seg.RFM_N_CLUSTERS} (documented business choice, see MODEL_CARD.md).")

    kmeans = seg.fit_rfm_kmeans(rfm_scaled)
    rfm["Cluster"] = kmeans.labels_
    rfm, cluster_label_map = seg.assign_business_segment_labels(rfm)
    seg.save_segmentation_artifacts(
        scaler, kmeans, cluster_label_map,
        PROJECT_ROOT / "artifacts" / "rfm_scaler.pkl", PROJECT_ROOT / "artifacts" / "rfm_kmeans.pkl",
    )
    rfm.to_csv(PROJECT_ROOT / "results" / "rfm_cluster_summary.csv", index=False)

    cluster_summary = rfm.groupby("Segment")[["Recency", "Frequency", "Monetary"]].mean().round(2)
    cluster_summary["customer_count"] = rfm["Segment"].value_counts()
    write_json(PROJECT_ROOT / "results" / "rfm_segments.json", {
        "cluster_label_map": cluster_label_map,
        "segment_summary": cluster_summary.reset_index().to_dict(orient="records"),
        "n_customers": int(len(rfm)),
    })
    print("Cluster label map:", cluster_label_map)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Olist analytics pipeline end to end.")
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "raw"))
    parser.add_argument("--clean", action="store_true", help="Clean raw tables and build canonical enriched datasets")
    parser.add_argument("--build-features", action="store_true", help="Alias for --clean (both stages run together)")
    parser.add_argument("--translate", action="store_true", help="Translate reviews (skips rows already translated)")
    parser.add_argument("--eda", action="store_true", help="Run the EDA suite")
    parser.add_argument("--segment", action="store_true", help="Run RFM customer segmentation")
    parser.add_argument("--allow-external-downloads", action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    orders_enriched = None

    if args.clean or args.build_features:
        result = stage_clean_and_build_features(data_dir)
        orders_enriched = result["orders_enriched"]

    if args.translate:
        if not args.allow_external_downloads:
            print("Skipping --translate: pass --allow-external-downloads to permit downloading the translation model.")
        else:
            from app.ml.translation import DEFAULT_CACHE_PATH, translate_reviews
            reviews_path = data_dir / "olist_order_reviews_dataset.csv"
            reviews = pd.read_csv(reviews_path)
            reviews = cleaning.clean_reviews(reviews)
            _, manifest = translate_reviews(reviews, checkpoint_path=PROJECT_ROOT / DEFAULT_CACHE_PATH)
            write_json(PROJECT_ROOT / "artifacts" / "translation_manifest.json", manifest.to_dict())

    if args.eda:
        if orders_enriched is None:
            processed_dir = PROJECT_ROOT / "data" / "processed"
            orders_enriched = pd.read_parquet(processed_dir / "orders_enriched.parquet")
        import subprocess
        subprocess.run([sys.executable, str(BACKEND_DIR / "scripts" / "run_eda.py")], check=True)

    if args.segment:
        if orders_enriched is None:
            processed_dir = PROJECT_ROOT / "data" / "processed"
            orders_enriched = pd.read_parquet(processed_dir / "orders_enriched.parquet")
        stage_segment(orders_enriched)

    if not any([args.clean, args.build_features, args.translate, args.eda, args.segment]):
        print("No stage flags given. Use --help to see available stages (--clean, --translate, --eda, --segment).")


if __name__ == "__main__":
    main()
