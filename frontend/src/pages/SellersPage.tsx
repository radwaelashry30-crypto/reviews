import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { LoadingState } from "../components/LoadingState";
import { useSellerPerformance, useSellerSummary } from "../hooks/useAnalytics";
import { formatCurrency, formatNumber, formatPercent } from "../utils/formatters";

export function SellersPage() {
  const summary = useSellerSummary();
  const performance = useSellerPerformance(20);

  return (
    <div className="page">
      <h1>Sellers</h1>

      {summary.loading && <LoadingState />}
      <ErrorState error={summary.error} />
      {summary.data && (
        <div className="kpi-grid">
          <KpiCard label="Total Sellers" value={formatNumber(summary.data.total_sellers)} />
          <KpiCard label="Avg Late-Delivery Rate" value={formatPercent(summary.data.avg_late_delivery_rate_pct)} />
          <KpiCard label="Avg Item Revenue / Seller" value={formatCurrency(summary.data.avg_item_revenue)} />
        </div>
      )}

      <section className="chart-card">
        <h2>Seller Delivery Performance (worst 20 by late-delivery rate)</h2>
        {performance.loading && <LoadingState />}
        <ErrorState error={performance.error} />
        {performance.data && (
          <table className="data-table">
            <thead><tr><th>Seller</th><th>Orders</th><th>Late-Delivery Rate</th><th>Item Revenue</th></tr></thead>
            <tbody>
              {performance.data.map((row) => (
                <tr key={String(row.seller_id)}>
                  <td>{String(row.seller_id).slice(0, 10)}...</td>
                  <td>{formatNumber(Number(row.order_count))}</td>
                  <td>{formatPercent(Number(row.late_delivery_rate) * 100)}</td>
                  <td>{formatCurrency(Number(row.item_revenue))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
