import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonthlyRevenuePoint } from "../../types/analytics";
import { CHART_AXIS, CHART_GOLD, CHART_GRID } from "./dashboard/dashboardChartColors";
import { DashboardChartTooltip } from "./dashboard/DashboardChartTooltip";
import { useChartTier } from "./dashboard/useChartTier";
import { pickTicks } from "./dashboard/responsiveTicks";

export function RevenueTrendChart({ data }: { data: MonthlyRevenuePoint[] }) {
  const tier = useChartTier();
  // See OrdersTrendChart for why this is the chart's own measured width
  // (via recharts' ResponsiveContainer onResize) rather than viewport width.
  const [containerWidth, setContainerWidth] = useState(600);
  const ticks = pickTicks(data.map((d) => d.order_year_month), containerWidth, tier);
  const height = tier === "mobile" ? 240 : tier === "tablet" ? 300 : 280;
  const fontSize = tier === "mobile" ? 12 : 11;

  return (
    <ResponsiveContainer width="100%" height={height} onResize={(width) => setContainerWidth(width)}>
      <AreaChart data={data} margin={{ top: 4, right: tier === "mobile" ? 32 : 28, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="revenue-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_GOLD} stopOpacity={0.5} />
            <stop offset="100%" stopColor={CHART_GOLD} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} vertical={tier !== "mobile"} />
        <XAxis dataKey="order_year_month" ticks={ticks} interval={0} tick={{ fontSize, fill: CHART_AXIS }} />
        <YAxis tick={{ fontSize, fill: CHART_AXIS }} width={tier === "mobile" ? 62 : 68} />
        <Tooltip content={<DashboardChartTooltip formatValue={(v) => `R$${v.toLocaleString()}`} />} />
        <Area type="monotone" dataKey="total_payment_value" stroke={CHART_GOLD} strokeWidth={2} fill="url(#revenue-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
