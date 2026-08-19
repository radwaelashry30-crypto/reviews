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

import itertools
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

logger = logging.getLogger(__name__)

RFM_N_CLUSTERS = 4  # a business decision (four segments map cleanly onto a marketing team's workflow), not a claimed analytical result -- see select_k() for the analytical evidence, saved to results/rfm_k_selection.json.
RFM_RANDOM_STATE = 42
RFM_N_INIT = 10
RFM_COLUMNS = ["Recency", "Frequency", "Monetary"]


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


def build_rfm_pipeline() -> Pipeline:
    """log1p then scale, fit and persisted as ONE object so the exact same
    transform is guaranteed to apply at both training and inference time.

    Without the log1p step, StandardScaler alone re-centers/re-scales but
    does nothing about Frequency's and Monetary's heavy right-skew (typical
    of e-commerce spend/order-count distributions) -- K-Means uses Euclidean
    distance, so untransformed outliers pull cluster centers toward them,
    producing one giant "everyone average" cluster plus a tiny "high spender"
    outlier cluster instead of behaviourally distinct segments. Verified on
    this dataset: pre-fix, 94% of customers landed in two clusters that were
    statistically indistinguishable on Frequency and Monetary, differing
    only on Recency -- see Technical Review #06/#07.
    """
    return Pipeline([
        ("log", FunctionTransformer(np.log1p, inverse_func=np.expm1, validate=True)),
        ("scale", StandardScaler()),
    ])


def scale_rfm_features(rfm: pd.DataFrame) -> tuple[np.ndarray, Pipeline]:
    pipeline = build_rfm_pipeline()
    scaled = pipeline.fit_transform(rfm[RFM_COLUMNS])
    return scaled, pipeline


def select_k(scaled: np.ndarray, k_range: range = range(2, 9), seed: int = RFM_RANDOM_STATE) -> tuple[int, list[dict]]:
    """Picks the k with the highest silhouette score over `k_range`, and
    returns the full curve as auditable evidence (see
    results/rfm_k_selection.json) -- an explicit, reviewable answer to
    "why k=N" instead of a bare hardcoded constant."""
    evidence = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=seed, n_init=RFM_N_INIT).fit(scaled)
        sample_size = min(10_000, len(scaled))
        evidence.append({
            "k": k,
            "inertia": float(km.inertia_),
            "silhouette": float(silhouette_score(scaled, km.labels_, sample_size=sample_size, random_state=seed)),
            "davies_bouldin": float(davies_bouldin_score(scaled, km.labels_)),
            "cluster_sizes": np.bincount(km.labels_).tolist(),
        })
    best = max(evidence, key=lambda e: e["silhouette"])
    return best["k"], evidence


def fit_rfm_kmeans(
    rfm_scaled, n_clusters: int = RFM_N_CLUSTERS, random_state: int = RFM_RANDOM_STATE, n_init: int = RFM_N_INIT,
) -> KMeans:
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=n_init)
    kmeans.fit(rfm_scaled)
    return kmeans


# Minimum relative gap on Monetary (and matching gap on Frequency) below
# which two clusters are considered "not actually behaviourally distinct" --
# see the stability guard in assign_business_segment_labels.
_MIN_MONETARY_SEPARATION = 0.10
_MIN_FREQUENCY_SEPARATION = 0.10


def assign_business_segment_labels(rfm: pd.DataFrame, cluster_col: str = "Cluster") -> tuple[pd.DataFrame, dict]:
    """Derive human-readable segment names from each cluster's FULL RFM
    profile (Recency + Frequency + Monetary ranks), not Monetary alone.

    The previous version ranked clusters by mean Monetary only, so two
    clusters that were nearly identical on Monetary and Frequency (and
    differed almost entirely on Recency, the dimension the old ranking never
    looked at) got assigned contradictory names ("At Risk" vs. "Potential
    Loyal") based on which side of a ~$0.24 gap they fell on -- a coin flip
    that could reverse under a different random seed. See Technical Review #06.
    """
    s = rfm.groupby(cluster_col)[RFM_COLUMNS].mean()
    r = 1 - s["Recency"].rank(pct=True)  # inverted: more recent = higher score
    f = s["Frequency"].rank(pct=True)
    m = s["Monetary"].rank(pct=True)

    def name_for(cid) -> str:
        R, F, M = r[cid], f[cid], m[cid]
        if F >= 0.75 and R >= 0.50:
            return "Loyal Customer"
        if M >= 0.75 and R >= 0.50:
            return "Champion"
        if M >= 0.75 and R < 0.50:
            return "Big Spender (Lapsing)"
        if R >= 0.75:
            return "Recent / Promising"
        if R < 0.25:
            return "At Risk"
        return "Needs Attention"

    cluster_label_map = {int(c): name_for(c) for c in s.index}

    if len(set(cluster_label_map.values())) < len(cluster_label_map):
        logger.warning(
            "Segment rules produced duplicate names: %s -- review thresholds or k "
            "(clusters may not be behaviourally distinct).", cluster_label_map,
        )

    for a, b in itertools.combinations(s.index, 2):
        monetary_rel = abs(s.loc[a, "Monetary"] - s.loc[b, "Monetary"]) / max(s.loc[a, "Monetary"], s.loc[b, "Monetary"], 1e-9)
        frequency_gap = abs(s.loc[a, "Frequency"] - s.loc[b, "Frequency"])
        if monetary_rel < _MIN_MONETARY_SEPARATION and frequency_gap < _MIN_FREQUENCY_SEPARATION:
            logger.warning(
                "Clusters %s and %s differ by only %.2f%% on Monetary and are nearly "
                "identical on Frequency -- their relative naming may be unstable across reruns.",
                a, b, monetary_rel * 100,
            )

    out = rfm.copy()
    out["Segment"] = out[cluster_col].map(cluster_label_map)
    return out, cluster_label_map


def save_segmentation_artifacts(
    scaler: Pipeline, kmeans: KMeans, cluster_label_map: dict,
    scaler_path: str | Path, kmeans_path: str | Path,
) -> None:
    Path(scaler_path).parent.mkdir(parents=True, exist_ok=True)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    with open(kmeans_path, "wb") as f:
        pickle.dump({"model": kmeans, "cluster_label_map": cluster_label_map}, f)


def load_segmentation_artifacts(scaler_path: str | Path, kmeans_path: str | Path) -> tuple[Pipeline, KMeans, dict]:
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)
    with open(kmeans_path, "rb") as f:
        payload = pickle.load(f)
    return scaler, payload["model"], payload["cluster_label_map"]


def predict_segment(scaler: Pipeline, kmeans: KMeans, cluster_label_map: dict, recency: float, frequency: float, monetary: float) -> dict:
    """Predict the RFM segment for a single (recency, frequency, monetary) input."""
    X = pd.DataFrame([[recency, frequency, monetary]], columns=RFM_COLUMNS)
    scaled = scaler.transform(X)
    cluster_id = int(kmeans.predict(scaled)[0])
    segment_name = cluster_label_map.get(cluster_id, cluster_label_map.get(str(cluster_id), "Unknown"))
    return {"cluster_id": cluster_id, "segment_name": segment_name}
