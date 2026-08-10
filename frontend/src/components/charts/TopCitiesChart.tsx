import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TopCity } from "../../types/analytics";
import { CHART_AXIS, CHART_GRID, GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function TopCitiesChart({ data }: { data: TopCity[] }) {
  const rows = [...data].sort((a, b) => a.order_count - b.order_count).map((r) => ({ ...r, label: titleCase(r.city) }));
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={rows} layout="vertical" margin={{ left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <YAxis type="category" dataKey="label" width={130} tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <Tooltip content={<ChartTooltip valueLabel="orders" />} cursor={{ fill: "rgba(201, 153, 46, 0.06)" }} />
        <Bar dataKey="order_count" fill={GOLD_SCALE[0]} radius={[0, 6, 6, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
