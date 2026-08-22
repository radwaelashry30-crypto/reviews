import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonthlyOrderPoint } from "../../types/analytics";
import { CHART_AXIS, CHART_BLUE, CHART_GRID } from "./dashboard/dashboardChartColors";
import { DashboardChartTooltip } from "./dashboard/DashboardChartTooltip";
import { useChartTier } from "./dashboard/useChartTier";
import { pickTicks } from "./dashboard/responsiveTicks";

export function OrdersTrendChart({ data }: { data: MonthlyOrderPoint[] }) {
  const tier = useChartTier();
  // This chart's own rendered width, not the viewport's -- Monthly orders
  // sits in a narrower card than Monthly revenue on every desktop
  // breakpoint, so it needs fewer ticks even on a wide screen. Recharts
  // already runs a ResizeObserver internally for `width="100%"`; `onResize`
  // just surfaces that same measurement instead of standing up a second one.
  const [containerWidth, setContainerWidth] = useState(360);
  const ticks = pickTicks(data.map((d) => d.order_year_month), containerWidth, tier);
  const height = tier === "mobile" ? 240 : tier === "tablet" ? 300 : 280;
  const fontSize = tier === "mobile" ? 12 : 11;

  return (
    <ResponsiveContainer width="100%" height={height} onResize={(width) => setContainerWidth(width)}>
      <AreaChart data={data} margin={{ top: 4, right: tier === "mobile" ? 32 : 28, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="orders-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_BLUE} stopOpacity={0.45} />
            <stop offset="100%" stopColor={CHART_BLUE} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} vertical={tier !== "mobile"} />
        <XAxis dataKey="order_year_month" ticks={ticks} interval={0} tick={{ fontSize, fill: CHART_AXIS }} />
        <YAxis tick={{ fontSize, fill: CHART_AXIS }} width={tier === "mobile" ? 38 : 46} />
        <Tooltip content={<DashboardChartTooltip valueLabel="orders" />} />
        <Area type="monotone" dataKey="order_count" stroke={CHART_BLUE} strokeWidth={2} fill="url(#orders-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
