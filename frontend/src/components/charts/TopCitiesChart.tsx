import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TopCity } from "../../types/analytics";
import { CHART_AXIS, CHART_BLUE, CHART_GRID } from "./dashboard/dashboardChartColors";
import { DashboardChartTooltip } from "./dashboard/DashboardChartTooltip";
import { useChartTier } from "./dashboard/useChartTier";

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

const MOBILE_VISIBLE = 6;

export function TopCitiesChart({ data }: { data: TopCity[] }) {
  const tier = useChartTier();
  const fontSize = tier === "mobile" ? 12 : 11;
  const rowHeight = tier === "mobile" ? 34 : 30;

  // Ranking is computed once, over the full dataset, before any display
  // truncation -- the mobile "Top N" caption never changes which cities
  // are actually top-ranked, only how many of them are drawn.
  const ranked = [...data].sort((a, b) => b.order_count - a.order_count);
  const visible = tier === "mobile" ? ranked.slice(0, MOBILE_VISIBLE) : ranked;
  const rows = [...visible].sort((a, b) => a.order_count - b.order_count).map((r) => ({ ...r, label: titleCase(r.city) }));

  return (
    <div>
      {visible.length < ranked.length && (
        <p className="bsr-caption bsr-dash-chart-note">Showing top {visible.length} of {ranked.length}</p>
      )}
      <ResponsiveContainer width="100%" height={Math.max(220, rows.length * rowHeight + 40)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 24, right: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
          <XAxis type="number" tick={{ fontSize, fill: CHART_AXIS }} />
          <YAxis type="category" dataKey="label" width={tier === "mobile" ? 108 : 130} tick={{ fontSize, fill: CHART_AXIS }} />
          <Tooltip content={<DashboardChartTooltip valueLabel="orders" />} cursor={{ fill: "rgba(35, 199, 255, 0.06)" }} />
          <Bar dataKey="order_count" fill={CHART_BLUE} radius={[0, 6, 6, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
