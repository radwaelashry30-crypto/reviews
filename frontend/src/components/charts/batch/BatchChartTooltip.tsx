import type { TooltipProps } from "recharts";

/** Batch-Upload-only tooltip on the Baseera `--bsr-*` tokens -- wired only
 * into the 4 chart components that render exclusively on BatchUploadPage.
 * See DashboardChartTooltip.tsx for why each reskinned page gets its own
 * copy instead of sharing one across not-yet-reskinned pages. */
export function BatchChartTooltip({
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
