"""RFM customer segmentation. Extracted from notebook cells 110-111 (§5.6), grain-corrected.

The notebook computes RFM directly off the order-item-grain `df`
(`Frequency=("order_id","nunique")`, `Monetary=("total_payment_value","sum")`).
Because `total_payment_value` is repeated once per item row within an order,
summing it over item-grain rows for a multi-item order inflates Monetary by
exactly the item count for that order (an order with 3 items contributes
3x its true payment total). This module operates on `orders_enriched`
(one row per order) instead, so Frequency and Monetary are correct by
construction — no special-casing needed.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

RFM_N_CLUSTERS = 4
RFM_RANDOM_STATE = 42
RFM_N_INIT = 10


def build_rfm_table(orders_enriched: pd.DataFrame, snapshot_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per customer_unique_id: Recency (days), Frequency (unique orders), Monetary (sum of order-level payment).

    `orders_enriched` already has exactly one row per order_id, so
    `Frequency=("order_id","nunique")` and `Monetary=("total_payment_value","sum")`
    are correct without deduplication — each order's payment total is counted once.
    """
    if snapshot_date is None:
        snapshot_date = orders_enriched["order_purchase_timestamp"].max() + pd.Timedelta(days=1)

    rfm = orders_enriched.groupby("customer_unique_id").agg(
        Recency=("order_purchase_timestamp", lambda x: (snapshot_date - x.max()).days),
        Frequency=("order_id", "nunique"),
        Monetary=("total_payment_value", "sum"),
    ).reset_index()
    return rfm


def scale_rfm_features(rfm: pd.DataFrame) -> tuple[pd.DataFrame, StandardScaler]:
    scaler = StandardScaler()
    scaled = scaler.fit_transform(rfm[["Recency", "Frequency", "Monetary"]])
    return scaled, scaler


def fit_rfm_kmeans(
    rfm_scaled, n_clusters: int = RFM_N_CLUSTERS, random_state: int = RFM_RANDOM_STATE, n_init: int = RFM_N_INIT,
) -> KMeans:
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=n_init)
    kmeans.fit(rfm_scaled)
    return kmeans


def assign_business_segment_labels(rfm: pd.DataFrame, cluster_col: str = "Cluster") -> tuple[pd.DataFrame, dict]:
    """Derive human-readable segment names FROM the fitted clusters' own characteristics.

    Ranks clusters by mean Monetary value (descending) and assigns names in
    that order: highest spend -> "Champion", lowest -> "At Risk". The mapping
    is data-driven (computed from `rfm`), not a fixed cluster-id -> name table,
    so it stays correct if KMeans assigns different cluster ids on a re-run.
    """
    cluster_summary = rfm.groupby(cluster_col)[["Recency", "Frequency", "Monetary"]].mean()
    ranked_clusters = cluster_summary.sort_values("Monetary", ascending=False).index.tolist()
    labels_by_rank = ["Champion", "Loyal Customer", "Potential Loyal", "At Risk"]
    labels_by_rank = labels_by_rank[: len(ranked_clusters)]
    cluster_label_map = {int(cluster): labels_by_rank[i] for i, cluster in enumerate(ranked_clusters)}

    out = rfm.copy()
    out["Segment"] = out[cluster_col].map(cluster_label_map)
    return out, cluster_label_map


def save_segmentation_artifacts(
    scaler: StandardScaler, kmeans: KMeans, cluster_label_map: dict,
    scaler_path: str | Path, kmeans_path: str | Path,
) -> None:
    Path(scaler_path).parent.mkdir(parents=True, exist_ok=True)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    with open(kmeans_path, "wb") as f:
        pickle.dump({"model": kmeans, "cluster_label_map": cluster_label_map}, f)


def load_segmentation_artifacts(scaler_path: str | Path, kmeans_path: str | Path) -> tuple[StandardScaler, KMeans, dict]:
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)
    with open(kmeans_path, "rb") as f:
        payload = pickle.load(f)
    return scaler, payload["model"], payload["cluster_label_map"]


def predict_segment(scaler: StandardScaler, kmeans: KMeans, cluster_label_map: dict, recency: float, frequency: float, monetary: float) -> dict:
    """Predict the RFM segment for a single (recency, frequency, monetary) input."""
    scaled = scaler.transform([[recency, frequency, monetary]])
    cluster_id = int(kmeans.predict(scaled)[0])
    segment_name = cluster_label_map.get(cluster_id, cluster_label_map.get(str(cluster_id), "Unknown"))
    return {"cluster_id": cluster_id, "segment_name": segment_name}
