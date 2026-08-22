import { useMemo, useState } from "react";
import { RfmExplorer } from "../components/customers/RfmExplorer";
import { colorForSegment, colorsForSegments } from "../components/customers/segmentColors";
import { SegmentChart } from "../components/charts/SegmentChart";
import { Button } from "../components/ui/Button";
import { DemoDataBadge } from "../components/ui/DemoDataBadge";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { GlassCard } from "../components/ui/GlassCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { SurfaceCard } from "../components/ui/SurfaceCard";
import { useCustomerSummary, useTopCities } from "../hooks/useAnalytics";
import { useRfmSummary } from "../hooks/useSegmentation";
import { formatCurrency, formatNumber, formatPercent } from "../utils/formatters";
import type { RfmSegmentSummaryRow } from "../types/segmentation";
import "../styles/customers.css";

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8;` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function segmentsToCsv(rows: RfmSegmentSummaryRow[], total: number): string {
  const header = "segment,customer_count,pct_of_customers,avg_recency_days,avg_frequency,avg_monetary_brl\n";
  const body = rows
    .map((r) => {
      const pct = total > 0 ? ((r.customer_count / total) * 100).toFixed(2) : "0.00";
      return [`"${r.Segment}"`, r.customer_count, pct, r.Recency.toFixed(2), r.Frequency.toFixed(2), r.Monetary.toFixed(2)].join(",");
    })
    .join("\n");
  return header + body;
}

/** Everything that depends on live data, isolated so a "Try again" click can
 * force a full remount (useAsync has no refetch capability -- see Phase 3A's
 * DashboardPage for the same documented constraint) without touching the
 * shared useAnalytics/useSegmentation hook files other pages also depend on. */
function CustomersData({ onRetry }: { onRetry: () => void }) {
  const summary = useCustomerSummary();
  const rfm = useRfmSummary();
  const topCities = useTopCities(10);
  const [selectedSegment, setSelectedSegment] = useState<string | null>(null);

  const anyError = summary.error || rfm.error || topCities.error;
  const anyLoading = summary.loading || rfm.loading || topCities.loading;

  const segmentRows = rfm.data?.segment_summary ?? [];
  const totalForPct = rfm.data?.n_customers ?? 0;
  const selectedRow = useMemo(
    () => segmentRows.find((r) => r.Segment === selectedSegment) ?? null,
    [segmentRows, selectedSegment],
  );

  if (anyLoading) {
    return (
      <SurfaceCard className="bsr-customers-panel">
        <div className="bsr-loading-state bsr-loading-state--full" role="status" aria-live="polite">
          <span className="bsr-btn__spinner bsr-loading-state__spinner" aria-hidden="true" style={{ width: 24, height: 24 }} />
          <span className="bsr-body">Loading customer intelligence…</span>
        </div>
      </SurfaceCard>
    );
  }

  if (anyError) {
    return (
      <SurfaceCard className="bsr-customers-panel">
        <ErrorState
          title="Couldn't load customer data"
          message={anyError.message}
          code={"code" in anyError ? anyError.code : undefined}
          onRetry={onRetry}
        />
      </SurfaceCard>
    );
  }

  if (!summary.data || !rfm.data) {
    return (
      <SurfaceCard className="bsr-customers-panel">
        <EmptyState title="No customer data available" description="Customer analytics have not been generated for this deployment yet." />
      </SurfaceCard>
    );
  }

  return (
    <>
      {/* KPIs -- every value maps 1:1 to a real customers/summary field. */}
      <section aria-label="Customer key metrics" className="bsr-customers-kpis">
        <SurfaceCard className="bsr-customers-kpi">
          <span className="bsr-customers-kpi__value bsr-mono">{formatNumber(summary.data.total_customers)}</span>
          <span className="bsr-customers-kpi__label bsr-label">Total customers</span>
        </SurfaceCard>
        <SurfaceCard className="bsr-customers-kpi">
          <span className="bsr-customers-kpi__value bsr-mono">{formatPercent(summary.data.repeat_customer_pct)}</span>
          <span className="bsr-customers-kpi__label bsr-label">Repeat purchase rate</span>
          <span className="bsr-customers-kpi__sub">customers with more than one order</span>
        </SurfaceCard>
        <SurfaceCard className="bsr-customers-kpi">
          <span className="bsr-customers-kpi__value bsr-mono">{summary.data.avg_orders_per_customer.toFixed(2)}</span>
          <span className="bsr-customers-kpi__label bsr-label">Avg orders / customer</span>
        </SurfaceCard>
        <SurfaceCard className="bsr-customers-kpi">
          <span className="bsr-customers-kpi__value bsr-mono">{formatCurrency(summary.data.avg_spend_per_customer)}</span>
          <span className="bsr-customers-kpi__label bsr-label">Avg spend / customer</span>
        </SurfaceCard>
      </section>

      {/* RFM / segments -- the page's central analytical section. */}
      <SectionHeader
        eyebrow="Segmentation"
        title="How customers group by recency, frequency, and monetary value"
        className="bsr-customers-section-head"
      />
      {segmentRows.length === 0 ? (
        <SurfaceCard className="bsr-customers-panel" style={{ marginBottom: "var(--bsr-space-6)" }}>
          <EmptyState title="No segments available" description="RFM segmentation has not been generated for this deployment yet." />
        </SurfaceCard>
      ) : (
        <div className="bsr-customers-segment-grid">
          <SurfaceCard className="bsr-customers-panel" aria-label="Customer segment composition, donut chart">
            <SegmentChart data={segmentRows} colors={colorsForSegments(segmentRows)} />
          </SurfaceCard>

          <SurfaceCard className="bsr-customers-panel">
            <h3 className="bsr-h5" style={{ marginTop: 0 }}>Segments</h3>
            <div className="bsr-customers-legend" role="list">
              {segmentRows.map((row) => {
                const pct = totalForPct > 0 ? (row.customer_count / totalForPct) * 100 : 0;
                const isActive = selectedSegment === row.Segment;
                return (
                  <button
                    key={row.Segment}
                    type="button"
                    role="listitem"
                    className={isActive ? "bsr-customers-legend__row bsr-customers-legend__row--active" : "bsr-customers-legend__row"}
                    aria-pressed={isActive}
                    onClick={() => setSelectedSegment(isActive ? null : row.Segment)}
                  >
                    <span className="bsr-customers-legend__swatch" aria-hidden="true" style={{ background: colorForSegment(row.Segment) }} />
                    <span className="bsr-customers-legend__name">{row.Segment}</span>
                    <span className="bsr-customers-legend__count">{formatNumber(row.customer_count)}</span>
                    <span className="bsr-customers-legend__pct">{pct.toFixed(1)}%</span>
                  </button>
                );
              })}
            </div>

            {selectedRow ? (
              <div className="bsr-customers-detail">
                <div className="bsr-customers-detail__head">
                  <h4 className="bsr-h5" style={{ margin: 0, color: colorForSegment(selectedRow.Segment) }}>{selectedRow.Segment}</h4>
                  <Button type="button" variant="ghost" onClick={() => setSelectedSegment(null)}>Clear selection</Button>
                </div>
                <div className="bsr-customers-detail__grid">
                  <div>
                    <div className="bsr-customers-detail__stat-value bsr-mono">{selectedRow.Recency.toFixed(0)} days</div>
                    <div className="bsr-customers-detail__stat-label bsr-label">Avg recency</div>
                  </div>
                  <div>
                    <div className="bsr-customers-detail__stat-value bsr-mono">{selectedRow.Frequency.toFixed(2)}</div>
                    <div className="bsr-customers-detail__stat-label bsr-label">Avg orders</div>
                  </div>
                  <div>
                    <div className="bsr-customers-detail__stat-value bsr-mono">{formatCurrency(selectedRow.Monetary)}</div>
                    <div className="bsr-customers-detail__stat-label bsr-label">Avg total spend</div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "var(--bsr-space-4)" }}>
                Select a segment above to see its average recency, order count, and spend.
              </p>
            )}

            <p className="bsr-sm bsr-customers-methodology">
              Recency, Frequency, and Monetary are computed per customer from their order history, then grouped into{" "}
              {segmentRows.length} segments by K-Means clustering (not fixed thresholds) and named from each cluster's
              relative rank on all three dimensions. Recency is measured in days before the day after this historical
              dataset's most recent order -- lower is more recent. Segment names describe clustering-derived behavior
              patterns, not individual predictions about any one customer.
            </p>

            <div className="bsr-customers-panel-actions" style={{ marginTop: "var(--bsr-space-3)" }}>
              <Button
                type="button"
                variant="ghost"
                onClick={() => downloadBlob("baseera-customer-segments.csv", segmentsToCsv(segmentRows, totalForPct), "text/csv")}
              >
                Export segment summary (CSV)
              </Button>
            </div>
          </SurfaceCard>
        </div>
      )}

      {/* RFM explorer -- the only genuine per-profile interaction this data supports. */}
      <SectionHeader
        eyebrow="Explore"
        title="Classify a hypothetical customer profile"
        description="This runs the real trained segmentation model on numbers you enter -- it does not look up or represent any actual customer."
        className="bsr-customers-section-head"
      />
      <SurfaceCard className="bsr-customers-panel" style={{ marginBottom: "var(--bsr-space-6)" }}>
        <RfmExplorer />
      </SurfaceCard>

      {/* Top cities -- unchanged real data, restyled. */}
      <SectionHeader eyebrow="Geography" title="Top cities by order count" className="bsr-customers-section-head" />
      <SurfaceCard className="bsr-customers-panel">
        {topCities.data && topCities.data.length > 0 ? (
          <table className="bsr-customers-cities-table">
            <thead>
              <tr><th>City</th><th className="bsr-mono">Orders</th></tr>
            </thead>
            <tbody>
              {topCities.data.map((row) => (
                <tr key={row.city}>
                  <td className="bsr-customers-city-name">{row.city}</td>
                  <td className="bsr-mono">{formatNumber(row.order_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="No city data yet" />
        )}
      </SurfaceCard>
    </>
  );
}

export function CustomersPage() {
  const [retryKey, setRetryKey] = useState(0);

  return (
    <div className="bsr-customers">
      <header className="bsr-customers-intro">
        <span className="bsr-label bsr-customers-intro__eyebrow">Customer Intelligence</span>
        <h1 className="bsr-h1">Understand your customer base</h1>
        <p className="bsr-body-lg">
          Real spend, repeat-purchase, and RFM segmentation metrics computed from this marketplace's historical order
          history -- who's buying, how often, and how customers group by behavior.
        </p>
        <div className="bsr-customers-intro__notes">
          <DemoDataBadge kind="historical" label="Historical Olist data · Jan 2017 – Aug 2018" />
        </div>
      </header>

      <CustomersData key={retryKey} onRetry={() => setRetryKey((k) => k + 1)} />
    </div>
  );
}
