import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { LoadingState } from "../components/LoadingState";
import { CategoryPerformanceChart } from "../components/charts/CategoryPerformanceChart";
import { OrdersTrendChart } from "../components/charts/OrdersTrendChart";
import { PaymentDistributionChart } from "../components/charts/PaymentDistributionChart";
import { RevenueTrendChart } from "../components/charts/RevenueTrendChart";
import { ReviewDistributionChart } from "../components/charts/ReviewDistributionChart";
import { SegmentChart } from "../components/charts/SegmentChart";
import { TopCitiesChart } from "../components/charts/TopCitiesChart";
import {
  useBusinessSummary, useCategoryPerformance, useMonthlyOrders, useMonthlyRevenue, usePaymentDistribution,
  useReviewDistribution, useTopCities,
} from "../hooks/useAnalytics";
import { useRfmSummary } from "../hooks/useSegmentation";
import { formatCurrency, formatNumber, formatPercent } from "../utils/formatters";

export function DashboardPage() {
  const summary = useBusinessSummary();
  const monthlyOrders = useMonthlyOrders();
  const monthlyRevenue = useMonthlyRevenue();
  const reviewDist = useReviewDistribution();
  const rfm = useRfmSummary();
  const payments = usePaymentDistribution();
  const topCities = useTopCities(10);
  const categories = useCategoryPerformance();

  return (
    <div className="page">
      <span className="eyebrow">Overview</span>
      <h1>How the marketplace is doing</h1>
      <p className="page-subtitle">Live figures from Olist's order, customer, and review data — grain-corrected, not row-inflated.</p>

      {summary.loading && <LoadingState label="Loading KPIs..." />}
      <ErrorState error={summary.error} />
      {summary.data && (
        <div className="kpi-grid">
          <KpiCard label="Unique Orders" value={formatNumber(summary.data.total_unique_orders)} />
          <KpiCard label="Customers" value={formatNumber(summary.data.total_unique_customers)} />
          <KpiCard label="Sellers" value={formatNumber(summary.data.total_unique_sellers)} />
          <KpiCard
            label="Order Payment Revenue (delivered)"
            value={formatCurrency(summary.data.total_order_payment_revenue_delivered)}
          />
          <KpiCard
            label="Avg Review Score"
            value={summary.data.avg_review_score ? summary.data.avg_review_score.toFixed(2) : "n/a"}
          />
          <KpiCard label="Late Delivery Rate" value={formatPercent(summary.data.late_delivery_rate_pct)} />
        </div>
      )}

      <div className="chart-grid">
        <section className="chart-card">
          <h2>Monthly Orders</h2>
          {monthlyOrders.loading && <LoadingState />}
          <ErrorState error={monthlyOrders.error} />
          {monthlyOrders.data && <OrdersTrendChart data={monthlyOrders.data} />}
        </section>

        <section className="chart-card">
          <h2>Monthly Revenue</h2>
          {monthlyRevenue.loading && <LoadingState />}
          <ErrorState error={monthlyRevenue.error} />
          {monthlyRevenue.data && <RevenueTrendChart data={monthlyRevenue.data} />}
        </section>

        <section className="chart-card">
          <h2>Review Score Distribution</h2>
          {reviewDist.loading && <LoadingState />}
          <ErrorState error={reviewDist.error} />
          {reviewDist.data && <ReviewDistributionChart data={reviewDist.data} />}
        </section>

        <section className="chart-card">
          <h2>RFM Segments</h2>
          {rfm.loading && <LoadingState />}
          <ErrorState error={rfm.error} />
          {rfm.data && <SegmentChart data={rfm.data.segment_summary} />}
        </section>

        <section className="chart-card">
          <h2>Payment Methods</h2>
          {payments.loading && <LoadingState />}
          <ErrorState error={payments.error} />
          {payments.data && <PaymentDistributionChart data={payments.data} />}
        </section>

        <section className="chart-card">
          <h2>Top Customer Cities</h2>
          {topCities.loading && <LoadingState />}
          <ErrorState error={topCities.error} />
          {topCities.data && <TopCitiesChart data={topCities.data} />}
        </section>

        <section className="chart-card" style={{ gridColumn: "1 / -1" }}>
          <h2>Top Product Categories by Revenue</h2>
          {categories.loading && <LoadingState />}
          <ErrorState error={categories.error} />
          {categories.data && <CategoryPerformanceChart data={categories.data} limit={10} />}
        </section>
      </div>
    </div>
  );
}
