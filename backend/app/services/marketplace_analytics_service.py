"""Builds every derived artifact (compact JSONB aggregates + typed entity
analytics rows) for one candidate dataset version, from its already-staged
marketplace_canonical_rows.

All aggregation is pushed to PostgreSQL via GROUP BY, never pandas -- this
keeps peak Python memory bounded to the size of the *aggregated* result sets
(one row per customer/seller/product), not the full canonical table. Every
order-grain field (payment_value, review_score, order_status, ...) is
deduplicated to one-row-per-order BEFORE being summed, mirroring the
existing, tested anti-inflation pattern in app/ml/segmentation.py and
app/ml/feature_engineering.py (summing payment_value directly over
item-grain rows inflates it by the item count of multi-item orders -- see
segmentation.py's module docstring for the historical bug this avoids).
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.segmentation import RFM_COLUMNS, load_segmentation_artifacts
from app.repositories import marketplace_repository as repo
from app.services.marketplace_import_service import build_availability_matrix

REQUIRED_ARTIFACTS = repo.REQUIRED_ARTIFACTS


def _rows(session: Session, sql: str, **params) -> list[dict]:
    result = session.execute(text(sql), params)
    return [dict(r._mapping) for r in result]


def build_overview_kpis(session: Session, version_id: str) -> dict:
    order_grain = _rows(session, """
        WITH order_grain AS (
            SELECT order_id, customer_unique_id,
                   MIN(payment_value) AS payment_value,
                   MIN(review_score) AS review_score,
                   MIN(order_delivered_customer_date) AS delivered_at,
                   MIN(order_estimated_delivery_date) AS estimated_at
            FROM marketplace_canonical_rows
            WHERE dataset_version_id = :vid
            GROUP BY order_id, customer_unique_id
        )
        SELECT
            COUNT(*) AS total_orders,
            COUNT(DISTINCT customer_unique_id) AS total_customers,
            COALESCE(SUM(payment_value), 0) AS total_revenue,
            AVG(review_score) AS avg_review_score,
            AVG(CASE WHEN delivered_at IS NULL OR estimated_at IS NULL THEN NULL
                     WHEN delivered_at > estimated_at THEN 1.0 ELSE 0.0 END) AS late_delivery_rate
        FROM order_grain
    """, vid=version_id)
    repeat = _rows(session, """
        WITH per_customer AS (
            SELECT customer_unique_id, COUNT(DISTINCT order_id) AS n
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid
            GROUP BY customer_unique_id
        )
        SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE n > 1) AS repeat
        FROM per_customer
    """, vid=version_id)
    o = order_grain[0]
    r = repeat[0]
    repeat_rate = (r["repeat"] / r["total"] * 100) if r["total"] else None
    return {
        "available": True,
        "total_orders": o["total_orders"],
        "total_customers": o["total_customers"],
        "total_revenue": float(o["total_revenue"]) if o["total_revenue"] is not None else 0.0,
        "avg_review_score": float(o["avg_review_score"]) if o["avg_review_score"] is not None else None,
        "late_delivery_rate_pct": float(o["late_delivery_rate"]) * 100 if o["late_delivery_rate"] is not None else None,
        "repeat_customer_rate_pct": repeat_rate,
    }


def build_monthly_trends(session: Session, version_id: str) -> dict:
    rows = _rows(session, """
        WITH order_grain AS (
            SELECT order_id, MIN(order_purchase_timestamp) AS ts, MIN(payment_value) AS payment_value
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid
            GROUP BY order_id
        )
        SELECT to_char(date_trunc('month', ts), 'YYYY-MM') AS month,
               COUNT(*) AS order_count, COALESCE(SUM(payment_value), 0) AS revenue
        FROM order_grain GROUP BY 1 ORDER BY 1
    """, vid=version_id)
    return {"available": bool(rows), "points": [{"month": r["month"], "order_count": r["order_count"], "revenue": float(r["revenue"])} for r in rows]}


def build_review_distribution(session: Session, version_id: str, fields_present: dict) -> dict:
    if not fields_present.get("review_score"):
        return {"available": False, "reason": "review_score not mapped in the uploaded dataset."}
    rows = _rows(session, """
        WITH order_grain AS (
            SELECT order_id, MIN(review_score) AS review_score
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid
            GROUP BY order_id
        )
        SELECT review_score, COUNT(*) AS n FROM order_grain
        WHERE review_score IS NOT NULL GROUP BY review_score ORDER BY review_score
    """, vid=version_id)
    return {"available": True, "counts": {str(int(r["review_score"])): r["n"] for r in rows}}


def build_payment_distribution(session: Session, version_id: str, fields_present: dict) -> dict:
    if not fields_present.get("main_payment_type"):
        return {"available": False, "reason": "main_payment_type not mapped in the uploaded dataset -- never falls back to a historical distribution."}
    rows = _rows(session, """
        WITH order_grain AS (
            SELECT order_id, MIN(main_payment_type) AS main_payment_type
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid
            GROUP BY order_id
        )
        SELECT main_payment_type, COUNT(*) AS n FROM order_grain
        WHERE main_payment_type IS NOT NULL GROUP BY main_payment_type ORDER BY n DESC
    """, vid=version_id)
    payload = {"available": True, "records": {r["main_payment_type"]: r["n"] for r in rows}}
    if fields_present.get("payment_installments"):
        inst = _rows(session, """
            WITH order_grain AS (
                SELECT order_id, MIN(payment_installments) AS payment_installments
                FROM marketplace_canonical_rows WHERE dataset_version_id = :vid GROUP BY order_id
            )
            SELECT AVG(payment_installments) AS avg_installments, MAX(payment_installments) AS max_installments
            FROM order_grain WHERE payment_installments IS NOT NULL
        """, vid=version_id)[0]
        payload["installments"] = {
            "available": True,
            "avg": float(inst["avg_installments"]) if inst["avg_installments"] is not None else None,
            "max": inst["max_installments"],
        }
    else:
        payload["installments"] = {"available": False, "reason": "payment_installments not mapped in the uploaded dataset."}
    return payload


def build_geography(session: Session, version_id: str, fields_present: dict) -> dict:
    if not (fields_present.get("customer_state")):
        return {"available": False, "reason": "customer_state not mapped in the uploaded dataset."}
    rows = _rows(session, """
        WITH order_grain AS (
            SELECT order_id, MIN(customer_state) AS customer_state, MIN(payment_value) AS payment_value
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid GROUP BY order_id
        )
        SELECT customer_state, COUNT(*) AS order_count, COALESCE(SUM(payment_value), 0) AS revenue
        FROM order_grain WHERE customer_state IS NOT NULL GROUP BY customer_state ORDER BY order_count DESC
    """, vid=version_id)
    return {"available": True, "by_customer_state": [{"state": r["customer_state"], "order_count": r["order_count"], "revenue": float(r["revenue"])} for r in rows]}


def build_rfm(session: Session, version_id: str, fields_present: dict) -> tuple[dict, list[dict]]:
    """Returns (rfm_segment_summary artifact, typed customer analytics rows
    WITHOUT rfm_segment merged in yet -- caller merges). Implements the
    approved RFM behavior exactly: uploaded dataset's own max(order_purchase_
    timestamp)+1day as the recency snapshot, existing historical scaler/
    kmeans in transform/predict mode only (never refit), factual
    out-of-training-distribution percentage (no invented pass/fail
    threshold), segment charts always shown with the limitation surfaced."""
    if not fields_present.get("payment_value"):
        return {"available": False, "reason": "payment_value not mapped -- RFM Monetary cannot be computed."}, []

    customer_rows = _rows(session, """
        WITH order_grain AS (
            SELECT order_id, customer_unique_id, customer_city, customer_state,
                   MIN(order_purchase_timestamp) AS order_purchase_timestamp,
                   MIN(payment_value) AS payment_value
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid
            GROUP BY order_id, customer_unique_id, customer_city, customer_state
        )
        SELECT customer_unique_id,
               COUNT(*) AS order_count,
               COALESCE(SUM(payment_value), 0) AS total_spend,
               MIN(order_purchase_timestamp) AS first_order_at,
               MAX(order_purchase_timestamp) AS last_order_at,
               MAX(customer_city) AS customer_city,
               MAX(customer_state) AS customer_state
        FROM order_grain GROUP BY customer_unique_id
    """, vid=version_id)
    if not customer_rows:
        return {"available": False, "reason": "No customers found in this version."}, []

    snapshot_date = max(r["last_order_at"] for r in customer_rows)
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)
    from datetime import timedelta
    snapshot_date = snapshot_date + timedelta(days=1)

    for r in customer_rows:
        last = r["last_order_at"]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        r["recency"] = float((snapshot_date - last).days)
        r["frequency"] = float(r["order_count"])
        r["monetary"] = float(r["total_spend"])

    try:
        scaler, kmeans, cluster_label_map = load_segmentation_artifacts(settings.RFM_SCALER_PATH, settings.RFM_MODEL_PATH)
    except Exception as e:
        return {"available": False, "reason": f"Historical RFM model artifacts unavailable: {e}"}, customer_rows

    import pandas as pd
    X = pd.DataFrame([[r["recency"], r["frequency"], r["monetary"]] for r in customer_rows], columns=RFM_COLUMNS)
    scaled = scaler.transform(X)
    cluster_ids = kmeans.predict(scaled)

    # Factual out-of-training-distribution diagnostic, derived from the
    # fitted scaler's OWN stored statistics -- not an invented threshold.
    # The "scale" step's post-log1p mean_/scale_ define the training
    # distribution; a 3-sigma z-score cutoff is a standard, non-arbitrary
    # statistical convention for flagging outliers, not a business rule.
    log_scaled = scaler.named_steps["log"].transform(X.to_numpy())
    z = (log_scaled - scaler.named_steps["scale"].mean_) / scaler.named_steps["scale"].scale_
    out_of_range = (np.abs(z) > 3).any(axis=1)

    for i, r in enumerate(customer_rows):
        cid = int(cluster_ids[i])
        r["rfm_segment"] = cluster_label_map.get(cid, cluster_label_map.get(str(cid), "Unknown"))
        r["rfm_out_of_distribution"] = bool(out_of_range[i])

    pct_out = float(out_of_range.mean() * 100)
    segment_summary: dict[str, dict] = {}
    for r in customer_rows:
        seg = segment_summary.setdefault(r["rfm_segment"], {"customer_count": 0, "recency_sum": 0.0, "frequency_sum": 0.0, "monetary_sum": 0.0})
        seg["customer_count"] += 1
        seg["recency_sum"] += r["recency"]
        seg["frequency_sum"] += r["frequency"]
        seg["monetary_sum"] += r["monetary"]
    segments_out = [
        {
            "segment": name, "customer_count": s["customer_count"],
            "avg_recency_days": s["recency_sum"] / s["customer_count"],
            "avg_frequency": s["frequency_sum"] / s["customer_count"],
            "avg_monetary": s["monetary_sum"] / s["customer_count"],
        }
        for name, s in segment_summary.items()
    ]
    artifact = {
        "available": True,
        "model_source": "historical_fitted_scaler_kmeans",  # never refit -- see docstring
        "snapshot_date": snapshot_date.isoformat(),
        "segments": segments_out,
        "limitation": (
            f"{pct_out:.1f}% of customers in this dataset fall more than 3 standard deviations from the "
            "historical training distribution (in at least one of Recency/Frequency/Monetary, measured in "
            "log-space against the original fitted scaler). This model was fit on the historical Olist dataset "
            "and is applied here in transform/predict mode only -- it was never refit on this data. Segment "
            "assignments may be less meaningful for a dataset that differs substantially from that distribution."
        ),
        "pct_customers_out_of_training_distribution": pct_out,
    }
    return artifact, customer_rows


def build_seller_analytics(session: Session, version_id: str, fields_present: dict) -> list[dict]:
    if not fields_present.get("seller_id"):
        return []
    return _rows(session, """
        SELECT seller_id,
               COUNT(DISTINCT order_id) AS order_count,
               COUNT(*) AS item_count,
               COALESCE(SUM(price), 0) AS item_revenue,
               COALESCE(AVG(price), 0) AS average_item_value,
               AVG(CASE WHEN order_delivered_customer_date IS NULL OR order_estimated_delivery_date IS NULL THEN NULL
                        WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1.0 ELSE 0.0 END) AS late_delivery_rate,
               COUNT(DISTINCT product_id) AS product_count,
               COUNT(DISTINCT product_category_name) AS category_count,
               MAX(seller_city) AS seller_city, MAX(seller_state) AS seller_state
        FROM marketplace_canonical_rows
        WHERE dataset_version_id = :vid AND seller_id IS NOT NULL
        GROUP BY seller_id
    """, vid=version_id)


def build_product_analytics(session: Session, version_id: str, fields_present: dict) -> list[dict]:
    if not fields_present.get("product_id"):
        return []
    base = _rows(session, """
        SELECT product_id, MAX(product_category_name) AS product_category_name,
               COUNT(*) AS item_count, COALESCE(SUM(price), 0) AS item_revenue,
               COALESCE(AVG(price), 0) AS average_item_price, COALESCE(SUM(freight_value), 0) AS freight_value
        FROM marketplace_canonical_rows
        WHERE dataset_version_id = :vid AND product_id IS NOT NULL
        GROUP BY product_id
    """, vid=version_id)
    if not fields_present.get("review_score") or not fields_present.get("product_category_name"):
        for r in base:
            r["associated_single_category_order_review_average"] = None
            r["associated_review_order_count"] = 0
            r["associated_review_excluded_order_count"] = 0
        return base

    reviews = _rows(session, """
        WITH order_categories AS (
            SELECT order_id, COUNT(DISTINCT product_category_name) AS n_categories
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid AND product_id IS NOT NULL
            GROUP BY order_id
        ),
        order_reviews AS (
            SELECT order_id, MIN(review_score) AS review_score
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid GROUP BY order_id
        ),
        product_orders AS (
            SELECT DISTINCT product_id, order_id
            FROM marketplace_canonical_rows WHERE dataset_version_id = :vid AND product_id IS NOT NULL
        )
        SELECT po.product_id,
            AVG(CASE WHEN oc.n_categories <= 1 THEN orv.review_score END) AS associated_single_category_order_review_average,
            COUNT(DISTINCT CASE WHEN oc.n_categories <= 1 AND orv.review_score IS NOT NULL THEN po.order_id END) AS associated_review_order_count,
            COUNT(DISTINCT CASE WHEN oc.n_categories > 1 THEN po.order_id END) AS associated_review_excluded_order_count
        FROM product_orders po
        JOIN order_categories oc ON oc.order_id = po.order_id
        LEFT JOIN order_reviews orv ON orv.order_id = po.order_id
        GROUP BY po.product_id
    """, vid=version_id)
    review_by_product = {r["product_id"]: r for r in reviews}
    for r in base:
        rv = review_by_product.get(r["product_id"])
        r["associated_single_category_order_review_average"] = float(rv["associated_single_category_order_review_average"]) if rv and rv["associated_single_category_order_review_average"] is not None else None
        r["associated_review_order_count"] = rv["associated_review_order_count"] if rv else 0
        r["associated_review_excluded_order_count"] = rv["associated_review_excluded_order_count"] if rv else 0
    return base


def build_and_store_all(session: Session, version_id: str, fields_present: dict) -> None:
    """Computes every required aggregate artifact and typed entity table for
    a candidate version and stores them. Called BEFORE activation is
    attempted -- activate_version() then verifies every REQUIRED_ARTIFACTS
    name is present and refuses to activate a version missing any of them
    or missing canonical rows entirely."""
    overview = build_overview_kpis(session, version_id)
    monthly = build_monthly_trends(session, version_id)
    reviews_dist = build_review_distribution(session, version_id, fields_present)
    payment_dist = build_payment_distribution(session, version_id, fields_present)
    geography = build_geography(session, version_id, fields_present)
    rfm_artifact, customer_rows = build_rfm(session, version_id, fields_present)
    availability = build_availability_matrix(fields_present)

    repo.upsert_derived_artifact(session, version_id=version_id, artifact_name="overview_kpis", payload=overview)
    repo.upsert_derived_artifact(session, version_id=version_id, artifact_name="monthly_trends", payload=monthly)
    repo.upsert_derived_artifact(session, version_id=version_id, artifact_name="review_distribution", payload=reviews_dist)
    repo.upsert_derived_artifact(session, version_id=version_id, artifact_name="payment_distribution", payload=payment_dist)
    repo.upsert_derived_artifact(session, version_id=version_id, artifact_name="rfm_segment_summary", payload=rfm_artifact)
    repo.upsert_derived_artifact(session, version_id=version_id, artifact_name="geography", payload=geography)
    repo.upsert_derived_artifact(session, version_id=version_id, artifact_name="availability_matrix", payload=availability)
    repo.upsert_derived_artifact(session, version_id=version_id, artifact_name="dataset_metadata", payload={
        "available": True, "dataset_version_id": version_id, "computed_at": datetime.now(timezone.utc).isoformat(),
    })

    chunk = settings.MARKETPLACE_CHUNK_ROWS
    if customer_rows:
        clean = [{
            "dataset_version_id": version_id, "customer_unique_id": r["customer_unique_id"],
            "order_count": r["order_count"], "total_spend": r["total_spend"],
            "average_order_value": (r["total_spend"] / r["order_count"]) if r["order_count"] else 0,
            "first_order_at": r["first_order_at"], "last_order_at": r["last_order_at"],
            "recency": r.get("recency"), "frequency": r.get("frequency"), "monetary": r.get("monetary"),
            "rfm_segment": r.get("rfm_segment"), "rfm_out_of_distribution": r.get("rfm_out_of_distribution"),
            "customer_city": r["customer_city"], "customer_state": r["customer_state"],
        } for r in customer_rows]
        for i in range(0, len(clean), chunk):
            repo.bulk_insert_customer_analytics(session, clean[i:i + chunk])

    sellers = build_seller_analytics(session, version_id, fields_present)
    if sellers:
        clean = [{**r, "dataset_version_id": version_id} for r in sellers]
        for i in range(0, len(clean), chunk):
            repo.bulk_insert_seller_analytics(session, clean[i:i + chunk])

    products = build_product_analytics(session, version_id, fields_present)
    if products:
        clean = [{**r, "dataset_version_id": version_id} for r in products]
        for i in range(0, len(clean), chunk):
            repo.bulk_insert_product_analytics(session, clean[i:i + chunk])
