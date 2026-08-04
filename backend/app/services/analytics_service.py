"""Business-KPI and analytics business logic, reading from `AnalyticsRepository`.

No large Pandas transformations happen here at request time — everything is
either a precomputed JSON lookup or a light aggregation over an already-loaded
DataFrame (loaded once at startup).
"""
from __future__ import annotations

from app.core.exceptions import ResourceNotFoundError
from app.repositories.analytics_repository import AnalyticsRepository


def get_business_summary(repo: AnalyticsRepository) -> dict:
    payload = repo.get_json("business_kpis")
    if payload is None:
        raise ResourceNotFoundError("Business KPI summary has not been generated yet. Run run_pipeline.py first.")
    return payload


def get_monthly_orders(repo: AnalyticsRepository) -> list[dict]:
    payload = repo.get_json("monthly_orders")
    return payload["records"] if payload else []


def get_monthly_revenue(repo: AnalyticsRepository) -> list[dict]:
    payload = repo.get_json("monthly_revenue")
    return payload["records"] if payload else []


def get_review_distribution(repo: AnalyticsRepository) -> dict:
    payload = repo.get_json("review_distribution")
    return payload["records"] if payload else {}


def get_delivery_summary(repo: AnalyticsRepository) -> dict:
    payload = repo.get_json("delivery_summary")
    if payload is None:
        raise ResourceNotFoundError("Delivery summary has not been generated yet.")
    return payload


def get_payment_distribution(repo: AnalyticsRepository) -> dict:
    payload = repo.get_json("payment_distribution")
    return payload["records"] if payload else {}


def get_customer_summary(repo: AnalyticsRepository) -> dict:
    customers = repo.get_dataframe("customers_enriched")
    if customers is None:
        raise ResourceNotFoundError("customers_enriched dataset is not loaded.")
    return {
        "total_customers": int(customers["customer_unique_id"].nunique()),
        "repeat_customer_pct": round(float(customers["is_repeat_customer"].mean() * 100), 2),
        "avg_orders_per_customer": round(float(customers["order_count"].mean()), 3),
        "avg_spend_per_customer": round(float(customers["total_spend"].mean()), 2),
    }


def get_top_cities(repo: AnalyticsRepository, n: int = 10) -> list[dict]:
    orders = repo.get_dataframe("orders_enriched")
    if orders is None:
        raise ResourceNotFoundError("orders_enriched dataset is not loaded.")
    top = orders.groupby("customer_city")["order_id"].nunique().sort_values(ascending=False).head(n)
    return [{"city": city, "order_count": int(count)} for city, count in top.items()]


def get_seller_summary(repo: AnalyticsRepository) -> dict:
    sellers = repo.get_dataframe("sellers_enriched")
    if sellers is None:
        raise ResourceNotFoundError("sellers_enriched dataset is not loaded.")
    return {
        "total_sellers": int(sellers["seller_id"].nunique()),
        "avg_late_delivery_rate_pct": round(float(sellers["late_delivery_rate"].mean() * 100), 2),
        "avg_item_revenue": round(float(sellers["item_revenue"].mean()), 2),
    }


def get_seller_performance(repo: AnalyticsRepository, n: int = 20) -> list[dict]:
    sellers = repo.get_dataframe("sellers_enriched")
    if sellers is None:
        raise ResourceNotFoundError("sellers_enriched dataset is not loaded.")
    top = sellers.sort_values("late_delivery_rate", ascending=False).head(n)
    return top.to_dict(orient="records")


def get_category_performance(repo: AnalyticsRepository) -> list[dict]:
    payload = repo.get_json("category_performance")
    return payload["records"] if payload else []


def get_state_performance(repo: AnalyticsRepository) -> list[dict]:
    payload = repo.get_json("state_performance")
    return payload["records"] if payload else []
