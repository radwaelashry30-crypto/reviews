import type { TooltipProps } from "recharts";

/**
 * Dashboard-only tooltip on the Baseera `--bsr-*` tokens. Not a replacement
 * for the shared `ChartTooltip` (which reads the legacy `--bg-elevated`/
 * `--border`/... vars and is still used by Sentiment, Batch Upload, and
 * Customers) -- those pages aren't reskinned yet, so their tooltip stays as
 * it was. This one is wired only into the 6 chart components that render
 * exclusively on DashboardPage.
 */
export function DashboardChartTooltip({
  active, payload, label, valueLabel, formatValue,
}: TooltipProps<number, string> & { valueLabel?: string; formatValue?: (v: number) => string }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: "var(--bsr-elevated)", border: "1px solid var(--bsr-border-strong)", borderRadius: "var(--bsr-radius-sm)",
        padding: "0.5rem 0.75rem", fontSize: "0.8rem", color: "var(--bsr-text)", boxShadow: "var(--bsr-shadow-md)",
      }}
    >
      {label !== undefined && <div style={{ color: "var(--bsr-text-faint)", marginBottom: "0.2rem", fontSize: "0.72rem" }}>{label}</div>}
      {payload.map((entry, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: entry.color, display: "inline-block" }} />
          <span>
            {formatValue ? formatValue(Number(entry.value)) : entry.value}
            {valueLabel ? ` ${valueLabel}` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}
