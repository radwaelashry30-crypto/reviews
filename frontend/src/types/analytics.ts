// Mirrors backend/app/schemas/analytics.py + the JSON shapes returned by analytics_service.py

export interface BusinessSummary {
  grain: string;
  total_unique_orders: number;
  total_unique_customers: number;
  total_unique_sellers: number;
  total_order_payment_revenue_delivered: number;
  total_item_revenue: number;
  avg_review_score: number | null;
  late_delivery_rate_pct: number;
  repeat_customer_rate_pct: number;
  order_status_distribution: Record<string, number>;
}

export interface MonthlyOrderPoint {
  order_year_month: string;
  order_count: number;
}

export interface MonthlyRevenuePoint {
  order_year_month: string;
  total_payment_value: number;
}

export interface DeliverySummary {
  late_delivery_rate: number;
  n_delivered: number;
  mean_days: number;
}

export interface ModelArtifactStatus {
  status: "available" | "unavailable" | "invalid" | "loading_failed";
  error?: string | null;
  [key: string]: unknown;
}

export interface ModelStatus {
  device: string;
  artifacts: Record<string, ModelArtifactStatus>;
}

export interface CustomerSummary {
  total_customers: number;
  repeat_customer_pct: number;
  avg_orders_per_customer: number;
  avg_spend_per_customer: number;
}

export interface TopCity {
  city: string;
  order_count: number;
}

export interface SellerSummary {
  total_sellers: number;
  avg_late_delivery_rate_pct: number;
  avg_item_revenue: number;
}
