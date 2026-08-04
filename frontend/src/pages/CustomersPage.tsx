import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { LoadingState } from "../components/LoadingState";
import { SegmentChart } from "../components/charts/SegmentChart";
import { useCustomerSummary, useTopCities } from "../hooks/useAnalytics";
import { useRfmSummary } from "../hooks/useSegmentation";
import { formatCurrency, formatNumber, formatPercent } from "../utils/formatters";

export function CustomersPage() {
  const summary = useCustomerSummary();
  const topCities = useTopCities(10);
  const rfm = useRfmSummary();

  return (
    <div className="page">
      <h1>Customers</h1>

      {summary.loading && <LoadingState />}
      <ErrorState error={summary.error} />
      {summary.data && (
        <div className="kpi-grid">
          <KpiCard label="Total Customers" value={formatNumber(summary.data.total_customers)} />
          <KpiCard label="Repeat Purchase Rate" value={formatPercent(summary.data.repeat_customer_pct)} />
          <KpiCard label="Avg Orders / Customer" value={summary.data.avg_orders_per_customer.toFixed(2)} />
          <KpiCard label="Avg Spend / Customer" value={formatCurrency(summary.data.avg_spend_per_customer)} />
        </div>
      )}

      <div className="chart-grid">
        <section className="chart-card">
          <h2>Top Cities by Orders</h2>
          {topCities.loading && <LoadingState />}
          <ErrorState error={topCities.error} />
          {topCities.data && (
            <table className="data-table">
              <thead><tr><th>City</th><th>Orders</th></tr></thead>
              <tbody>
                {topCities.data.map((row) => (
                  <tr key={row.city}><td>{row.city}</td><td>{formatNumber(row.order_count)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="chart-card">
          <h2>Customer Segments (RFM)</h2>
          {rfm.loading && <LoadingState />}
          <ErrorState error={rfm.error} />
          {rfm.data && <SegmentChart data={rfm.data.segment_summary} />}
        </section>
      </div>
    </div>
  );
}
