"""Unit tests for grain-correctness: an order with multiple items must not
inflate order-level counts, and payment/review values must not be summed
per-item. Uses small synthetic tables, not the full dataset."""
import pandas as pd

from app.ml.feature_engineering import (
    build_customers_enriched, build_order_items_enriched, build_orders_enriched, build_reviews_enriched,
    check_join_cardinality,
)


def _synthetic_tables():
    orders = pd.DataFrame({
        "order_id": ["o1", "o2"],
        "customer_id": ["c1", "c2"],
        "order_status": ["delivered", "delivered"],
        "order_purchase_timestamp": pd.to_datetime(["2018-01-01", "2018-01-05"]),
        "order_approved_at": pd.to_datetime(["2018-01-01", "2018-01-05"]),
        "order_delivered_carrier_date": pd.to_datetime(["2018-01-02", "2018-01-06"]),
        "order_delivered_customer_date": pd.to_datetime(["2018-01-05", "2018-01-10"]),
        "order_estimated_delivery_date": pd.to_datetime(["2018-01-10", "2018-01-12"]),
    })
    customers = pd.DataFrame({
        "customer_id": ["c1", "c2"],
        "customer_unique_id": ["u1", "u2"],
        "customer_zip_code_prefix": [1001, 1002],
        "customer_city": ["sao paulo", "rio"],
        "customer_state": ["SP", "RJ"],
    })
    # order o1 has TWO items -> payments/reviews must still be counted ONCE per order
    payments = pd.DataFrame({
        "order_id": ["o1", "o2"],
        "payment_sequential": [1, 1],
        "payment_type": ["credit_card", "boleto"],
        "payment_installments": [2, 1],
        "payment_value": [300.0, 50.0],
    })
    reviews = pd.DataFrame({
        "order_id": ["o1", "o2"],
        "review_score": [5, 3],
    })
    items = pd.DataFrame({
        "order_id": ["o1", "o1", "o2"],
        "order_item_id": [1, 2, 1],
        "product_id": ["p1", "p2", "p3"],
        "seller_id": ["s1", "s1", "s2"],
        "shipping_limit_date": pd.to_datetime(["2018-01-02"] * 3),
        "price": [100.0, 100.0, 50.0],
        "freight_value": [10.0, 10.0, 5.0],
    })
    products = pd.DataFrame({
        "product_id": ["p1", "p2", "p3"],
        "product_category_name": ["cat_a", "cat_a", "cat_b"],
        "product_name_lenght": [10, 10, 10],
        "product_description_lenght": [50, 50, 50],
        "product_photos_qty": [1, 1, 1],
        "product_weight_g": [500, 500, 500],
        "product_length_cm": [10, 10, 10],
        "product_height_cm": [10, 10, 10],
        "product_width_cm": [10, 10, 10],
    })
    sellers = pd.DataFrame({
        "seller_id": ["s1", "s2"],
        "seller_zip_code_prefix": [2001, 2002],
        "seller_city": ["campinas", "niteroi"],
        "seller_state": ["SP", "RJ"],
    })
    translation = pd.DataFrame({
        "product_category_name": ["cat_a", "cat_b"],
        "product_category_name_english": ["category_a", "category_b"],
    })
    return orders, customers, payments, reviews, items, products, sellers, translation


def test_orders_enriched_has_one_row_per_order():
    orders, customers, payments, reviews, items, products, sellers, translation = _synthetic_tables()
    orders_enriched = build_orders_enriched(orders, customers, payments, reviews)
    assert len(orders_enriched) == 2
    assert orders_enriched["order_id"].is_unique


def test_orders_enriched_payment_not_multiplied_by_item_count():
    orders, customers, payments, reviews, items, products, sellers, translation = _synthetic_tables()
    orders_enriched = build_orders_enriched(orders, customers, payments, reviews)
    o1_payment = orders_enriched.loc[orders_enriched["order_id"] == "o1", "total_payment_value"].iloc[0]
    # o1 has 2 items but ONE payment record of 300.0 -- must stay 300.0, not 600.0
    assert o1_payment == 300.0


def test_order_items_enriched_has_one_row_per_item():
    orders, customers, payments, reviews, items, products, sellers, translation = _synthetic_tables()
    order_items_enriched = build_order_items_enriched(items, products, sellers, translation)
    assert len(order_items_enriched) == 3  # o1 has 2 items + o2 has 1 item


def test_customers_enriched_frequency_uses_unique_orders():
    orders, customers, payments, reviews, items, products, sellers, translation = _synthetic_tables()
    orders_enriched = build_orders_enriched(orders, customers, payments, reviews)
    customers_enriched = build_customers_enriched(customers, orders_enriched)
    assert customers_enriched["order_count"].max() == 1  # each synthetic customer has exactly 1 order
    assert customers_enriched["customer_unique_id"].is_unique


def test_check_join_cardinality_detects_one_to_many():
    orders, customers, payments, reviews, items, products, sellers, translation = _synthetic_tables()
    result = check_join_cardinality(orders, items, on="order_id", how="left")
    assert result["relationship"] == "one-to-many"
    assert result["right_duplicate_keys"] > 0


def test_reviews_enriched_deduplicates_genuine_duplicate_review_ids():
    """Regression test: the raw Olist reviews CSV genuinely contains duplicate
    review_id rows (verified: 827/100,000 in the real dataset, e.g. a resent
    review survey). build_reviews_enriched must deduplicate them, not just
    assert uniqueness and crash on real data."""
    reviews = pd.DataFrame({
        "review_id": ["r1", "r1", "r2"],  # r1 duplicated, as happens in the real raw file
        "order_id": ["o1", "o1", "o2"],
        "review_score": [5, 5, 3],
    })
    out = build_reviews_enriched(reviews)
    assert len(out) == 2
    assert out["review_id"].is_unique


def test_row_count_over_counts_orders_when_using_item_grain():
    """Demonstrates the exact failure mode this project's grain-correct
    functions avoid: counting order_status directly off an item-grain frame."""
    orders, customers, payments, reviews, items, products, sellers, translation = _synthetic_tables()
    order_items_enriched = build_order_items_enriched(items, products, sellers, translation)
    item_grain_order_count = order_items_enriched["order_id"].count()  # WRONG: counts item rows
    correct_order_count = order_items_enriched["order_id"].nunique()  # RIGHT: unique orders
    assert item_grain_order_count == 3
    assert correct_order_count == 2
    assert item_grain_order_count != correct_order_count
