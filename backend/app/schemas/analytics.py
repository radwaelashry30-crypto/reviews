from __future__ import annotations

from pydantic import BaseModel


class BusinessSummary(BaseModel):
    grain: str
    total_unique_orders: int
    total_unique_customers: int
    total_unique_sellers: int
    total_order_payment_revenue_delivered: float
    total_item_revenue: float
    avg_review_score: float | None
    late_delivery_rate_pct: float
    repeat_customer_rate_pct: float
    order_status_distribution: dict[str, int]


class MonthlyOrderPoint(BaseModel):
    order_year_month: str
    order_count: int


class MonthlyRevenuePoint(BaseModel):
    order_year_month: str
    total_payment_value: float


class DeliverySummary(BaseModel):
    late_delivery_rate: float
    n_delivered: int
    mean_days: float


class ModelStatus(BaseModel):
    device: str
    artifacts: dict
