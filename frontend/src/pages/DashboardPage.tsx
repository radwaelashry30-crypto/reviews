import { ChartPanelState } from "../components/dashboard/ChartPanelState";
import { DemoDataBadge } from "../components/ui/DemoDataBadge";
import { SectionHeader } from "../components/ui/SectionHeader";
import { SurfaceCard } from "../components/ui/SurfaceCard";
import { CategoryPerformanceChart } from "../components/charts/CategoryPerformanceChart";
import { OrdersTrendChart } from "../components/charts/OrdersTrendChart";
import { PaymentDistributionChart } from "../components/charts/PaymentDistributionChart";
import { RevenueTrendChart } from "../components/charts/RevenueTrendChart";
import { ReviewDistributionChart } from "../components/charts/ReviewDistributionChart";
import { SegmentChart } from "../components/charts/SegmentChart";
import { TopCitiesChart } from "../components/charts/TopCitiesChart";
import { BLUE_SCALE } from "../components/charts/dashboard/dashboardChartColors";
import {
  useBusinessSummary, useCategoryPerformance, useMonthlyOrders, useMonthlyRevenue, usePaymentDistribution,
  useReviewDistribution, useTopCities,
} from "../hooks/useAnalytics";
import { useRfmSummary } from "../hooks/useSegmentation";
import { formatCurrency, formatCurrencyCompact, formatNumber, formatPercent } from "../utils/formatters";
import "../styles/dashboard.css";

interface KpiItem {
  label: string;
  value: string;
  /** Full-precision value for the native tooltip + accessible label, when
   * `value` is a lossy compact form (e.g. "R$15.42M"). */
  exact?: string;
}

export function DashboardPage() {
  const summary = useBusinessSummary();
  const monthlyOrders = useMonthlyOrders();
  const monthlyRevenue = useMonthlyRevenue();
  const reviewDist = useReviewDistribution();
  const rfm = useRfmSummary();
  const payments = usePaymentDistribution();
  const topCities = useTopCities(10);
  const categories = useCategoryPerformance();

  const kpis: KpiItem[] = summary.data
    ? [
        { label: "Unique Orders", value: formatNumber(summary.data.total_unique_orders) },
        { label: "Customers", value: formatNumber(summary.data.total_unique_customers) },
        { label: "Sellers", value: formatNumber(summary.data.total_unique_sellers) },
        {
          label: "Order Payment Revenue (delivered)",
          value: formatCurrencyCompact(summary.data.total_order_payment_revenue_delivered),
          exact: formatCurrency(summary.data.total_order_payment_revenue_delivered),
        },
        { label: "Avg Review Score", value: summary.data.avg_review_score ? summary.data.avg_review_score.toFixed(2) : "n/a" },
        { label: "Late Delivery Rate", value: formatPercent(summary.data.late_delivery_rate_pct) },
      ]
    : [];

  return (
    <div className="bsr-dash">
      {/* 1. Introduction -- no repeated marketing hero, just an honest, concise framing. */}
      <header className="bsr-dash-intro">
        <span className="bsr-label bsr-dash-intro__eyebrow">Overview</span>
        <h1 className="bsr-h1">How the marketplace is doing</h1>
        <p className="bsr-body-lg">Orders, revenue, customers, and reviews from Olist's enriched, grain-corrected dataset.</p>
        <DemoDataBadge kind="historical" label="Historical Olist data · Jan 2017 – Aug 2018" className="bsr-dash-intro__badge" />
      </header>

      {/* 2. Primary metrics */}
      <section aria-label="Key metrics" className="bsr-dash-kpis-section">
        <ChartPanelState loading={summary.loading} error={summary.error} isEmpty={!summary.data} loadingLabel="Loading key metrics…" emptyTitle="No summary data yet">
          <div className="bsr-dash-kpis">
            {kpis.map((kpi) => (
              <SurfaceCard key={kpi.label} className="bsr-dash-kpi">
                <span
                  className="bsr-dash-kpi__value bsr-mono"
                  title={kpi.exact}
                  aria-label={kpi.exact ? `${kpi.value}, exact value ${kpi.exact}` : undefined}
                >
                  {kpi.value}
                </span>
                <span className="bsr-dash-kpi__label bsr-label">{kpi.label}</span>
              </SurfaceCard>
            ))}
          </div>
        </ChartPanelState>
      </section>

      {/* 3. Main analytical view -- revenue gets the largest visual weight, orders sits beside it as the paired trend. */}
      <section aria-labelledby="dash-analytics-heading" className="bsr-dash-analytics">
        <SurfaceCard className="bsr-dash-hero-panel" aria-label="Monthly order payment revenue, line chart">
          <div className="bsr-dash-panel-head">
            <div>
              <span className="bsr-label">Business health</span>
              <h2 id="dash-analytics-heading" className="bsr-h3">Monthly revenue</h2>
            </div>
          </div>
          <ChartPanelState
            loading={monthlyRevenue.loading}
            error={monthlyRevenue.error}
            isEmpty={!monthlyRevenue.data || monthlyRevenue.data.length === 0}
            loadingLabel="Loading revenue trend…"
            emptyTitle="No revenue data yet"
          >
            {monthlyRevenue.data && <RevenueTrendChart data={monthlyRevenue.data} />}
          </ChartPanelState>
        </SurfaceCard>

        <SurfaceCard className="bsr-dash-secondary-panel" aria-label="Monthly order count, area chart">
          <div className="bsr-dash-panel-head">
            <h2 className="bsr-h5">Monthly orders</h2>
          </div>
          <ChartPanelState
            loading={monthlyOrders.loading}
            error={monthlyOrders.error}
            isEmpty={!monthlyOrders.data || monthlyOrders.data.length === 0}
            loadingLabel="Loading order trend…"
            emptyTitle="No order data yet"
          >
            {monthlyOrders.data && <OrdersTrendChart data={monthlyOrders.data} />}
          </ChartPanelState>
        </SurfaceCard>
      </section>

      {/* 4. Supporting insights -- grouped by theme, varied layout rather than one uniform grid. */}
      <SectionHeader eyebrow="Customer signals" title="Satisfaction and customer value" className="bsr-dash-group-header" />
      <section aria-label="Review score distribution and customer segments" className="bsr-dash-insight-row">
        <SurfaceCard aria-label="Review score distribution, bar chart">
          <div className="bsr-dash-panel-head">
            <h3 className="bsr-h5">Review score distribution</h3>
          </div>
          <ChartPanelState
            loading={reviewDist.loading}
            error={reviewDist.error}
            isEmpty={!reviewDist.data || Object.keys(reviewDist.data).length === 0}
            loadingLabel="Loading review scores…"
            emptyTitle="No review data yet"
          >
            {reviewDist.data && <ReviewDistributionChart data={reviewDist.data} />}
          </ChartPanelState>
        </SurfaceCard>

        <SurfaceCard aria-label="RFM customer segments, donut chart">
          <div className="bsr-dash-panel-head">
            <h3 className="bsr-h5">RFM segments</h3>
          </div>
          <ChartPanelState
            loading={rfm.loading}
            error={rfm.error}
            isEmpty={!rfm.data || rfm.data.segment_summary.length === 0}
            loadingLabel="Loading customer segments…"
            emptyTitle="No segment data yet"
          >
            {rfm.data && <SegmentChart data={rfm.data.segment_summary} colors={BLUE_SCALE} />}
          </ChartPanelState>
        </SurfaceCard>
      </section>

      <SectionHeader eyebrow="Commerce" title="Payments and where customers are" className="bsr-dash-group-header" />
      <section aria-label="Payment method distribution and top customer cities" className="bsr-dash-insight-row">
        <SurfaceCard aria-label="Payment method distribution, donut chart">
          <div className="bsr-dash-panel-head">
            <h3 className="bsr-h5">Payment methods</h3>
          </div>
          <ChartPanelState
            loading={payments.loading}
            error={payments.error}
            isEmpty={!payments.data || Object.keys(payments.data).length === 0}
            loadingLabel="Loading payment methods…"
            emptyTitle="No payment data yet"
          >
            {payments.data && <PaymentDistributionChart data={payments.data} />}
          </ChartPanelState>
        </SurfaceCard>

        <SurfaceCard aria-label="Top customer cities, horizontal bar chart">
          <div className="bsr-dash-panel-head">
            <h3 className="bsr-h5">Top customer cities</h3>
          </div>
          <ChartPanelState
            loading={topCities.loading}
            error={topCities.error}
            isEmpty={!topCities.data || topCities.data.length === 0}
            loadingLabel="Loading top cities…"
            emptyTitle="No city data yet"
          >
            {topCities.data && <TopCitiesChart data={topCities.data} />}
          </ChartPanelState>
        </SurfaceCard>
      </section>

      <SurfaceCard className="bsr-dash-full-panel" aria-label="Top product categories by revenue, horizontal bar chart">
        <div className="bsr-dash-panel-head">
          <div>
            <span className="bsr-label">Products</span>
            <h3 className="bsr-h4">Top categories by revenue</h3>
          </div>
        </div>
        <ChartPanelState
          loading={categories.loading}
          error={categories.error}
          isEmpty={!categories.data || categories.data.length === 0}
          loadingLabel="Loading category performance…"
          emptyTitle="No category data yet"
        >
          {categories.data && <CategoryPerformanceChart data={categories.data} limit={10} />}
        </ChartPanelState>
      </SurfaceCard>
    </div>
  );
}
