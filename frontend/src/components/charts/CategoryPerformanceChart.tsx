import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_AXIS, CHART_GOLD, CHART_GRID } from "./dashboard/dashboardChartColors";
import { DashboardChartTooltip } from "./dashboard/DashboardChartTooltip";
import { useChartTier } from "./dashboard/useChartTier";

function formatCategoryName(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const MOBILE_VISIBLE = 6;

export function CategoryPerformanceChart({ data, limit = 10 }: { data: Record<string, unknown>[]; limit?: number }) {
  const tier = useChartTier();
  const fontSize = tier === "mobile" ? 12 : 11;
  const rowHeight = tier === "mobile" ? 34 : 30;

  // Ranking is computed once, over the full (limit-capped) dataset, before
  // any mobile display truncation -- the "Top N" caption never changes
  // which categories are actually top-ranked, only how many are drawn.
  const ranked = [...data]
    .map((row) => ({
      label: formatCategoryName(String(row.product_category_name_english ?? "unknown")),
      revenue: Number(row.price ?? 0),
    }))
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, limit);
  const visible = tier === "mobile" ? ranked.slice(0, MOBILE_VISIBLE) : ranked;
  const rows = [...visible].reverse();

  return (
    <div>
      {visible.length < ranked.length && (
        <p className="bsr-caption bsr-dash-chart-note">Showing top {visible.length} of {ranked.length}</p>
      )}
      <ResponsiveContainer width="100%" height={Math.max(220, rows.length * rowHeight + 40)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 24, right: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
          <XAxis type="number" tick={{ fontSize, fill: CHART_AXIS }} tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`} />
          <YAxis type="category" dataKey="label" width={tier === "mobile" ? 116 : 140} tick={{ fontSize, fill: CHART_AXIS }} />
          <Tooltip content={<DashboardChartTooltip formatValue={(v) => `R$${v.toLocaleString()}`} />} cursor={{ fill: "rgba(244, 185, 66, 0.06)" }} />
          <Bar dataKey="revenue" fill={CHART_GOLD} radius={[0, 6, 6, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
