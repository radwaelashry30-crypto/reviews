"""Relational joins and feature engineering, at explicit, documented grains.

The original notebook (cells 42-47) builds one merged dataframe at
order-item grain: `orders -> customers -> items -> products -> sellers ->
payment summary -> review summary`. Because an order can contain multiple
items, that dataframe repeats every order-level field (total_payment_value,
order_status, review_score, ...) once per item row. The notebook's own EDA
cells then compute several KPIs directly off that dataframe's row count
(`df.groupby("order_year_month").size()`, `df["main_payment_type"]` pie
counts, etc), which over-counts orders whenever an order has more than one
item. See DATA_GRAIN_AUDIT.md for the measured impact (verified on the
project's actual cleaned dataset: 112,650 order-item rows vs. 98,666 unique
orders, a ~14.2% inflation on row-count-based order tallies).

This module keeps that original merged dataframe available as
`build_legacy_merged_dataframe()` for notebook-reproduction purposes, but
adds grain-correct canonical datasets for everything else:

- `orders_enriched`      — one row per unique order_id
- `order_items_enriched` — one row per order item (product/price granularity)
- `reviews_enriched`     — one row per review
- `customers_enriched`   — one row per unique customer_unique_id
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import state_name_to_region


# ---------------------------------------------------------------------------
# Order-level aggregation helpers (notebook cell 42)
# ---------------------------------------------------------------------------

def build_payment_summary(payments: pd.DataFrame) -> pd.DataFrame:
    """One row per order: total payment value (summed across installments/sequentials).

    `payment_value` is summed by `payment_sequential` within an order (e.g. a
    customer paying partly by voucher, partly by credit card), NOT by item —
    the payments table has no `order_item_id`, so this total already
    represents one value per order and must not be re-summed later.
    """
    return (
        payments.groupby("order_id", as_index=False)["payment_value"]
        .sum()
        .rename(columns={"payment_value": "total_payment_value"})
    )


def build_payment_type_summary(payments: pd.DataFrame) -> pd.DataFrame:
    """One row per order: the most frequent payment_type used for that order."""
    return (
        payments.groupby("order_id")["payment_type"]
        .agg(lambda x: x.value_counts().idxmax())
        .reset_index()
        .rename(columns={"payment_type": "main_payment_type"})
    )


def build_installments_summary(payments: pd.DataFrame) -> pd.DataFrame:
    """One row per order: the maximum installment count used."""
    return payments.groupby("order_id", as_index=False)["payment_installments"].max()


def build_review_summary(reviews: pd.DataFrame) -> pd.DataFrame:
    """One row per order: mean review score (an order can have >1 review record)."""
    return reviews.groupby("order_id", as_index=False)["review_score"].mean()


def translate_categories(products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    return pd.merge(products, translation, on="product_category_name", how="left")


# ---------------------------------------------------------------------------
# Join-cardinality validation
# ---------------------------------------------------------------------------

class JoinCardinalityWarning(RuntimeWarning):
    pass


def check_join_cardinality(left: pd.DataFrame, right: pd.DataFrame, on: str, how: str) -> dict:
    """Report whether a join key is unique on each side, to catch accidental
    many-to-many merges before they silently multiply rows."""
    left_dupes = int(left[on].duplicated().sum())
    right_dupes = int(right[on].duplicated().sum())
    if left_dupes == 0 and right_dupes == 0:
        relationship = "one-to-one"
    elif left_dupes > 0 and right_dupes == 0:
        relationship = "many-to-one"
    elif left_dupes == 0 and right_dupes > 0:
        relationship = "one-to-many"
    else:
        relationship = "many-to-many"
    return {
        "on": on,
        "how": how,
        "left_rows": len(left),
        "right_rows": len(right),
        "left_duplicate_keys": left_dupes,
        "right_duplicate_keys": right_dupes,
        "relationship": relationship,
    }


# ---------------------------------------------------------------------------
# Feature functions, split by grain
# ---------------------------------------------------------------------------

def add_order_level_features(orders: pd.DataFrame) -> pd.DataFrame:
    """Delivery duration/delay, calendar features. Notebook cell 47, order grain.

    `delivery_days`/`delivery_delay_days` stay NaN for orders with no
    `order_delivered_customer_date` (canceled/unavailable orders) — these are
    real business facts, not imputed, per the notebook's own documented
    decision (§2.3) not to fabricate delivery dates for orders that never shipped.
    """
    out = orders.copy()
    out["order_purchase_timestamp"] = pd.to_datetime(out["order_purchase_timestamp"])
    out["order_delivered_customer_date"] = pd.to_datetime(out["order_delivered_customer_date"])
    out["order_estimated_delivery_date"] = pd.to_datetime(out["order_estimated_delivery_date"])

    out["delivery_days"] = (out["order_delivered_customer_date"] - out["order_purchase_timestamp"]).dt.days
    out["delivery_delay_days"] = (out["order_delivered_customer_date"] - out["order_estimated_delivery_date"]).dt.days
    out["is_late_delivery"] = out["delivery_delay_days"] > 0

    out["order_hour"] = out["order_purchase_timestamp"].dt.hour
    out["order_day"] = out["order_purchase_timestamp"].dt.day_name()
    out["order_year_month"] = out["order_purchase_timestamp"].dt.to_period("M").astype(str)
    return out


def add_price_outlier_flag(items: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
    """IQR-based outlier flag on item price. Notebook cell 47. Flags, never removes rows."""
    out = items.copy()
    q1, q3 = out[price_col].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    out["is_price_outlier"] = (out[price_col] < lower) | (out[price_col] > upper)
    return out


def add_delay_bucket(df: pd.DataFrame, delay_col: str = "delivery_delay_days") -> pd.DataFrame:
    """Bucket delivery delay into notebook §5.4's bins. Any grain with `delay_col` present."""
    out = df.copy()
    out["delay_bucket"] = pd.cut(
        out[delay_col],
        bins=[-100, 0, 5, 15, 100],
        labels=["Early/On-time", "0-5 days late", "5-15 days late", "15+ days late"],
    )
    return out


def add_customer_order_counts(orders_enriched: pd.DataFrame) -> pd.DataFrame:
    """customer_order_count = distinct orders per customer_unique_id (order grain)."""
    counts = orders_enriched.groupby("customer_unique_id")["order_id"].transform("nunique")
    out = orders_enriched.copy()
    out["customer_order_count"] = counts
    return out


def add_seller_late_delivery_rate(order_items_enriched: pd.DataFrame, orders_enriched: pd.DataFrame) -> pd.DataFrame:
    """seller_late_delivery_rate: share of a seller's ORDERS (not items) delivered late.

    Computed at order grain per seller to avoid weighting a seller's rate by
    how many items happened to be in each order.
    """
    item_order = order_items_enriched[["order_id", "seller_id"]].drop_duplicates()
    merged = item_order.merge(
        orders_enriched[["order_id", "is_late_delivery"]], on="order_id", how="left"
    )
    rate = merged.groupby("seller_id")["is_late_delivery"].mean().rename("seller_late_delivery_rate")
    out = order_items_enriched.merge(rate, on="seller_id", how="left")
    return out


# ---------------------------------------------------------------------------
# Canonical enriched datasets
# ---------------------------------------------------------------------------

def build_orders_enriched(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    payments: pd.DataFrame,
    reviews: pd.DataFrame,
) -> pd.DataFrame:
    """One row per unique order_id: order status/dates + customer + payment + review aggregate.

    This is the correct grain for: order counts, monthly order trend, revenue
    (payment-based), delivery performance, late-delivery rate, and any KPI
    that must not be multiplied by item count.
    """
    payment_summary = build_payment_summary(payments)
    payment_type = build_payment_type_summary(payments)
    installments = build_installments_summary(payments)
    review_summary = build_review_summary(reviews)

    out = orders.merge(customers, on="customer_id", how="left")
    out = out.merge(payment_summary, on="order_id", how="left")
    out = out.merge(payment_type, on="order_id", how="left")
    out = out.merge(installments, on="order_id", how="left")
    out = out.merge(review_summary, on="order_id", how="left")

    out = add_order_level_features(out)
    out["customer_state_name"] = out["customer_state"].astype(str)
    out["region"] = out["customer_state_name"].map(state_name_to_region)

    out["total_payment_value"] = out["total_payment_value"].fillna(0.0)
    out["main_payment_type"] = out["main_payment_type"].fillna("not_defined")
    out["payment_installments"] = out["payment_installments"].fillna(1)

    assert out["order_id"].is_unique, "orders_enriched must have exactly one row per order_id"
    return out


def build_order_items_enriched(
    items: pd.DataFrame,
    products: pd.DataFrame,
    sellers: pd.DataFrame,
    translation: pd.DataFrame,
) -> pd.DataFrame:
    """One row per order item: product/seller attributes + price-outlier flag.

    Correct grain for: category revenue (sum of item `price`), item-level
    freight analysis, and per-seller item volume. Do NOT use this table to
    count orders or sum order-level payment totals.
    """
    products_en = translate_categories(products, translation)
    products_en["product_category_name_english"] = products_en["product_category_name_english"].fillna("Unknown")
    products_en["product_category_name"] = products_en["product_category_name"].fillna("Unknown")

    out = items.merge(products_en, on="product_id", how="left")
    out = out.merge(sellers, on="seller_id", how="left")
    out = add_price_outlier_flag(out, price_col="price")
    out["seller_state_name"] = out["seller_state"].astype(str)
    return out


def build_reviews_enriched(reviews: pd.DataFrame, orders_enriched: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per review_id. Optionally attaches order-level delay bucket for review analysis.

    The raw `olist_order_reviews_dataset.csv` genuinely contains duplicate
    `review_id` rows (verified: 827 duplicate rows out of 100,000, e.g. a
    resent review survey landing as a second identical-id record) — this is
    NOT introduced by this function's own merge. Deduplicating on
    `review_id` (keep first) here is what actually makes the "one row per
    review_id" grain guarantee true; the merge with `orders_enriched` below
    is many-to-one on `order_id` and cannot itself create duplicate
    `review_id`s.
    """
    out = reviews.drop_duplicates(subset="review_id", keep="first").copy()
    if orders_enriched is not None:
        out = out.merge(
            orders_enriched[["order_id", "delivery_delay_days", "is_late_delivery", "customer_state_name", "region"]],
            on="order_id", how="left",
        )
        out = add_delay_bucket(out, delay_col="delivery_delay_days")
    assert out["review_id"].is_unique, "reviews_enriched must have exactly one row per review_id"
    return out


def build_customers_enriched(customers: pd.DataFrame, orders_enriched: pd.DataFrame) -> pd.DataFrame:
    """One row per unique customer_unique_id: order count, spend, first/last order date.

    `customer_id` in the raw Olist data is actually one-per-order (a Olist
    modeling quirk); `customer_unique_id` is the real, stable customer entity
    and is what all customer-level KPIs (repeat-purchase rate, RFM) must use.
    """
    per_order = orders_enriched.groupby("customer_unique_id").agg(
        order_count=("order_id", "nunique"),
        total_spend=("total_payment_value", "sum"),
        first_order_at=("order_purchase_timestamp", "min"),
        last_order_at=("order_purchase_timestamp", "max"),
        avg_review_score=("review_score", "mean"),
    ).reset_index()
    per_order["is_repeat_customer"] = per_order["order_count"] > 1

    identity = customers.drop_duplicates("customer_unique_id")[
        ["customer_unique_id", "customer_city", "customer_state"]
    ]
    out = per_order.merge(identity, on="customer_unique_id", how="left")
    assert out["customer_unique_id"].is_unique, "customers_enriched must have exactly one row per customer_unique_id"
    return out


def build_sellers_enriched(order_items_enriched: pd.DataFrame, orders_enriched: pd.DataFrame) -> pd.DataFrame:
    """One row per seller_id: item volume, order volume, late-delivery rate."""
    item_order = order_items_enriched[["order_id", "seller_id", "price"]].drop_duplicates(subset=["order_id", "seller_id"], keep="first")
    order_join = item_order.merge(
        orders_enriched[["order_id", "is_late_delivery"]], on="order_id", how="left"
    )
    agg = order_join.groupby("seller_id").agg(
        order_count=("order_id", "nunique"),
        late_delivery_rate=("is_late_delivery", "mean"),
    ).reset_index()
    item_agg = order_items_enriched.groupby("seller_id").agg(
        item_count=("product_id", "count"),
        item_revenue=("price", "sum"),
    ).reset_index()
    out = agg.merge(item_agg, on="seller_id", how="left")
    assert out["seller_id"].is_unique, "sellers_enriched must have exactly one row per seller_id"
    return out


def build_legacy_merged_dataframe(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    items: pd.DataFrame,
    products: pd.DataFrame,
    sellers: pd.DataFrame,
    payments: pd.DataFrame,
    reviews: pd.DataFrame,
    translation: pd.DataFrame,
) -> pd.DataFrame:
    """Reproduces the notebook's single merged dataframe (cells 42-47) at order-item grain.

    Kept ONLY for reproducing the notebook's original EDA numbers. Do not use
    this for order-level KPIs (order counts, revenue, late-delivery %, etc) —
    it will over-count any order with more than one item. Use
    `build_orders_enriched` / `build_order_items_enriched` instead.
    """
    payments_summary = build_payment_summary(payments)
    payment_type_mode = build_payment_type_summary(payments)
    installments_summary = build_installments_summary(payments)
    reviews_summary = build_review_summary(reviews)
    products_en = translate_categories(products, translation)

    df = orders.merge(customers, on="customer_id", how="left")
    df = df.merge(items, on="order_id", how="left")
    df = df.merge(products_en, on="product_id", how="left")
    df = df.merge(sellers, on="seller_id", how="left")
    df = df.merge(payments_summary, on="order_id", how="left")
    df = df.merge(payment_type_mode, on="order_id", how="left")
    df = df.merge(installments_summary, on="order_id", how="left")
    df = df.merge(reviews_summary, on="order_id", how="left")

    df = df.dropna(subset=["product_id"])
    df["product_category_name_english"] = df["product_category_name_english"].fillna("Unknown")
    df["product_category_name"] = df["product_category_name"].fillna("Unknown")
    df["review_score"] = df["review_score"].fillna(0)
    df["total_payment_value"] = df["total_payment_value"].fillna(df["price"] + df["freight_value"])
    df["main_payment_type"] = df["main_payment_type"].fillna("not_defined")
    df["payment_installments"] = df["payment_installments"].fillna(1)

    df = add_order_level_features(df)
    df = add_price_outlier_flag(df, price_col="price")
    return df
