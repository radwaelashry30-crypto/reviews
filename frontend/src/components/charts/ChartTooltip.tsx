import type { TooltipProps } from "recharts";

/** Dark-themed tooltip shared by every chart (recharts' default is a white box, which clashes with the app's dark theme). */
export function ChartTooltip({
  active, payload, label, valueLabel, formatValue,
}: TooltipProps<number, string> & { valueLabel?: string; formatValue?: (v: number) => string }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)",
        padding: "0.5rem 0.75rem", fontSize: "0.8rem", color: "var(--text)", boxShadow: "var(--shadow-card)",
      }}
    >
      {label !== undefined && <div style={{ color: "var(--text-faint)", marginBottom: "0.2rem", fontSize: "0.72rem" }}>{label}</div>}
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
