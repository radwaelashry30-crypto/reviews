"""Exploratory analyses, reproducing notebook section 4-5 at the CORRECT data grain.

Every function takes its dataframe explicitly (no notebook globals), returns
its aggregated result as a DataFrame/dict, and optionally saves a figure when
`save_path` is given. None of these depend on Jupyter's `display()`.

Order-count/revenue/payment/delivery/review analyses use `orders_enriched`
(one row per order) instead of the notebook's order-item-grain `df`, per
DATA_GRAIN_AUDIT.md. Category-revenue analyses correctly use
`order_items_enriched` (item grain), since category revenue is a sum of item
prices, not an order-level KPI.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def _save_fig(fig, save_path: str | Path | None, as_html: bool = True) -> None:
    if save_path is None:
        return
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if as_html:
        fig.write_html(str(save_path))
    else:
        fig.savefig(save_path, bbox_inches="tight")


def order_status_distribution(orders_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.Series:
    """Order-status counts, one row per unique order_id."""
    counts = orders_enriched["order_status"].value_counts()
    try:
        import plotly.express as px
        fig = px.pie(values=counts.values, names=counts.index, title="Distribution of Order Statuses (unique orders)")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return counts


def monthly_orders_trend(orders_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.DataFrame:
    """Unique orders per calendar month."""
    filtered = orders_enriched.dropna(subset=["order_year_month"])
    monthly = filtered.groupby("order_year_month")["order_id"].nunique().reset_index(name="order_count")
    monthly = monthly.sort_values("order_year_month")
    try:
        import plotly.express as px
        fig = px.line(monthly, x="order_year_month", y="order_count", markers=True, title="Monthly Unique Orders")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return monthly


def top_cities_by_orders(orders_enriched: pd.DataFrame, n: int = 10, save_path: str | Path | None = None) -> pd.DataFrame:
    """Top N cities by unique order count (not row count)."""
    top = orders_enriched.groupby("customer_city")["order_id"].nunique().sort_values(ascending=False).head(n)
    top = top.reset_index(name="order_count")
    try:
        import plotly.express as px
        fig = px.bar(top, x="customer_city", y="order_count", title=f"Top {n} Cities by Unique Orders")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return top


def top_categories_by_revenue(order_items_enriched: pd.DataFrame, n: int = 10, save_path: str | Path | None = None) -> pd.DataFrame:
    """Top N categories by summed item price (item grain — correct for this KPI)."""
    top = (
        order_items_enriched.groupby("product_category_name_english")["price"]
        .sum().sort_values(ascending=False).head(n).reset_index()
    )
    try:
        import plotly.express as px
        fig = px.bar(top, x="price", y="product_category_name_english", orientation="h", title=f"Top {n} Categories by Item Revenue")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return top


def top_categories_by_failed_orders(
    orders_enriched: pd.DataFrame, order_items_enriched: pd.DataFrame, n: int = 10, save_path: str | Path | None = None
) -> pd.DataFrame:
    """Top N categories by count of DISTINCT failed orders (canceled/unavailable)."""
    failed_orders = orders_enriched.loc[orders_enriched["order_status"].isin(["canceled", "unavailable"]), "order_id"]
    failed_items = order_items_enriched[order_items_enriched["order_id"].isin(failed_orders)]
    top = (
        failed_items.drop_duplicates(subset=["order_id", "product_category_name_english"])
        .groupby("product_category_name_english")["order_id"].nunique()
        .sort_values(ascending=False).head(n).reset_index(name="failed_order_count")
    )
    try:
        import plotly.express as px
        fig = px.bar(top, x="failed_order_count", y="product_category_name_english", orientation="h", title=f"Top {n} Categories by Failed Orders")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return top


def review_score_distribution(orders_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.Series:
    """Review-score distribution at order grain (one score per order, matches reviews_enriched aggregate)."""
    dist = orders_enriched["review_score"].dropna().value_counts().sort_index()
    try:
        import plotly.express as px
        fig = px.pie(values=dist.values, names=[f"{s:.0f} Stars" for s in dist.index], title="Review Score Distribution")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return dist


def peak_shopping_heatmap(orders_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.DataFrame:
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    matrix = (
        orders_enriched.groupby(["order_day", "order_hour"])["order_id"].nunique()
        .reset_index(name="orders_count")
        .pivot(index="order_day", columns="order_hour", values="orders_count")
        .reindex(days_order)
    )
    try:
        import plotly.express as px
        fig = px.imshow(matrix, title="Peak Order Times (unique orders)")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return matrix


def delivery_time_distribution(orders_enriched: pd.DataFrame, save_path: str | Path | None = None) -> dict:
    delivered = orders_enriched.dropna(subset=["delivery_days"])
    late_rate = float(orders_enriched["is_late_delivery"].mean())
    try:
        import plotly.express as px
        fig = px.histogram(delivered, x="delivery_days", nbins=60, title="Delivery Time Distribution (days)")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return {"late_delivery_rate": late_rate, "n_delivered": int(len(delivered)), "mean_days": float(delivered["delivery_days"].mean())}


def late_delivery_rate_by_state(orders_enriched: pd.DataFrame, top_n: int = 15, save_path: str | Path | None = None) -> pd.DataFrame:
    d = orders_enriched.dropna(subset=["delivery_delay_days"]).copy()
    d["status"] = np.where(d["delivery_delay_days"] > 0, "Late", "On time")
    pivot = pd.pivot_table(d, index="customer_state_name", columns="status", values="order_id", aggfunc="count", fill_value=0)
    pivot = pivot.reindex(columns=["Late", "On time"], fill_value=0)
    pivot["late_pct"] = pivot["Late"] / pivot.sum(axis=1) * 100
    out = pivot.sort_values("late_pct", ascending=False).head(top_n).reset_index()
    try:
        import plotly.express as px
        fig = px.bar(out, x="customer_state_name", y="late_pct", title=f"Top {top_n} States by Late-Delivery Rate (%)")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return out


def seller_late_delivery_ranking(sellers_enriched: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    return sellers_enriched.sort_values("late_delivery_rate", ascending=False).head(top_n)


def review_score_by_delay_bucket(reviews_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.DataFrame:
    d = reviews_enriched.dropna(subset=["delay_bucket", "review_score"])
    summary = d.groupby("delay_bucket", observed=True)["review_score"].agg(["mean", "median", "std", "count"]).reset_index()
    try:
        import plotly.express as px
        fig = px.box(d, x="delay_bucket", y="review_score", title="Review Score by Delivery-Delay Bucket")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return summary


def payment_method_distribution(orders_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.Series:
    dist = orders_enriched["main_payment_type"].value_counts()
    try:
        import plotly.express as px
        fig = px.pie(values=dist.values, names=dist.index, title="Payment Method Distribution (unique orders)")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return dist


def installment_distribution(orders_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.Series:
    dist = orders_enriched["payment_installments"].value_counts().sort_index()
    try:
        import plotly.express as px
        fig = px.histogram(orders_enriched, x="payment_installments", nbins=24, title="Installments per Order")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return dist


def price_freight_outlier_summary(order_items_enriched: pd.DataFrame) -> pd.DataFrame:
    return order_items_enriched.groupby("is_price_outlier")["price"].describe()


def spearman_correlation(orders_enriched: pd.DataFrame, order_items_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.DataFrame:
    """Correlation across price/freight (item grain, one row per item) vs delivery/review (order grain).

    Aggregates item-level price/freight to order grain first (mean per order)
    so every row in the correlation matrix represents one order, avoiding the
    grain-mixing the notebook's single merged frame implicitly performed.
    """
    item_agg = order_items_enriched.groupby("order_id").agg(price=("price", "mean"), freight_value=("freight_value", "mean")).reset_index()
    merged = orders_enriched.merge(item_agg, on="order_id", how="inner")
    cols = ["price", "freight_value", "delivery_days", "delivery_delay_days", "payment_installments", "review_score"]
    corr = merged[cols].corr(method="spearman")
    try:
        import plotly.express as px
        fig = px.imshow(corr, text_auto=".2f", title="Spearman Correlation (order grain)")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return corr


def monthly_revenue_trend(orders_enriched: pd.DataFrame, save_path: str | Path | None = None) -> pd.DataFrame:
    """Monthly revenue from delivered orders, summed once per order (no item-count duplication)."""
    delivered = orders_enriched[orders_enriched["order_status"] == "delivered"]
    monthly = delivered.groupby("order_year_month")["total_payment_value"].sum().reset_index().sort_values("order_year_month")
    try:
        import plotly.express as px
        fig = px.line(monthly, x="order_year_month", y="total_payment_value", markers=True, title="Monthly Revenue (Delivered Orders)")
        _save_fig(fig, save_path)
    except ImportError:
        pass
    return monthly


def repeat_purchase_rate(customers_enriched: pd.DataFrame) -> dict:
    repeat_pct = float(customers_enriched["is_repeat_customer"].mean() * 100)
    return {"repeat_customer_pct": repeat_pct, "one_time_customer_pct": 100 - repeat_pct, "n_customers": int(len(customers_enriched))}


def compute_business_summary(
    orders_enriched: pd.DataFrame, order_items_enriched: pd.DataFrame,
    customers_enriched: pd.DataFrame, sellers_enriched: pd.DataFrame,
) -> dict:
    """The single JSON `results/business_kpis.json` backing `/api/v1/analytics/summary`.

    All counts/sums are computed off the grain-correct canonical datasets
    (see DATA_GRAIN_AUDIT.md) — `orders_enriched` is built directly from
    `orders`+`customers`+`payments`+`reviews` and therefore includes every
    order, including the ~775 orders with no matching `order_items` row
    (their `order_status` is disproportionately `canceled`/`unavailable` —
    an order that was canceled/unavailable often has no items ever
    allocated to it). This is intentionally different from, and more
    complete than, `legacy_order_item_merged`, which drops those rows to
    reproduce the notebook's own `dropna(subset=["product_id"])` step.
    """
    return {
        "grain": "orders_enriched (one row per unique order_id, includes orders with no order_items row) unless noted",
        "total_unique_orders": int(orders_enriched["order_id"].nunique()),
        "total_unique_customers": int(customers_enriched["customer_unique_id"].nunique()),
        "total_unique_sellers": int(sellers_enriched["seller_id"].nunique()),
        "total_order_payment_revenue_delivered": float(orders_enriched.loc[orders_enriched["order_status"] == "delivered", "total_payment_value"].sum()),
        "total_item_revenue": float(order_items_enriched["price"].sum()),
        "avg_review_score": float(orders_enriched["review_score"].replace(0, np.nan).mean()),
        "late_delivery_rate_pct": float(orders_enriched["is_late_delivery"].mean() * 100),
        "repeat_customer_rate_pct": float(customers_enriched["is_repeat_customer"].mean() * 100),
        "order_status_distribution": orders_enriched["order_status"].value_counts().to_dict(),
    }


def late_delivery_significance_test(orders_enriched: pd.DataFrame) -> dict:
    """Welch's t-test + Mann-Whitney U on review score, late vs on-time delivery. Notebook §4.12, order grain."""
    delivered = orders_enriched.dropna(subset=["delivery_delay_days", "review_score"])
    late_scores = delivered.loc[delivered["is_late_delivery"], "review_score"]
    ontime_scores = delivered.loc[~delivered["is_late_delivery"], "review_score"]

    t_stat, t_p = stats.ttest_ind(late_scores, ontime_scores, equal_var=False)
    u_stat, u_p = stats.mannwhitneyu(late_scores, ontime_scores, alternative="two-sided")

    pooled_std = np.sqrt((late_scores.var() + ontime_scores.var()) / 2)
    cohens_d = float((ontime_scores.mean() - late_scores.mean()) / pooled_std) if pooled_std > 0 else None

    alpha = 0.05
    return {
        "late_delivery": {"n": int(len(late_scores)), "mean": float(late_scores.mean()), "median": float(late_scores.median()), "std": float(late_scores.std())},
        "on_time_delivery": {"n": int(len(ontime_scores)), "mean": float(ontime_scores.mean()), "median": float(ontime_scores.median()), "std": float(ontime_scores.std())},
        "welch_t_test": {"statistic": float(t_stat), "p_value": float(t_p)},
        "mann_whitney_u_test": {"statistic": float(u_stat), "p_value": float(u_p)},
        "effect_size_cohens_d": cohens_d,
        "alpha": alpha,
        "statistically_significant": bool(u_p < alpha),
    }
