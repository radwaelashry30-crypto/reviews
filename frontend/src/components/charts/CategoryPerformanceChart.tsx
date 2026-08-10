import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_AXIS, CHART_GRID, GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

function formatCategoryName(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CategoryPerformanceChart({ data, limit = 10 }: { data: Record<string, unknown>[]; limit?: number }) {
  const rows = [...data]
    .map((row) => ({
      label: formatCategoryName(String(row.product_category_name_english ?? "unknown")),
      revenue: Number(row.price ?? 0),
    }))
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, limit)
    .reverse();

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={rows} layout="vertical" margin={{ left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: CHART_AXIS }} tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`} />
        <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <Tooltip content={<ChartTooltip formatValue={(v) => `R$${v.toLocaleString()}`} />} cursor={{ fill: "rgba(201, 153, 46, 0.06)" }} />
        <Bar dataKey="revenue" fill={GOLD_SCALE[1]} radius={[0, 6, 6, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
