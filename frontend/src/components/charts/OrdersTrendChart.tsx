import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonthlyOrderPoint } from "../../types/analytics";
import { CHART_AXIS, CHART_GRID, GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

export function OrdersTrendChart({ data }: { data: MonthlyOrderPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="orders-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={GOLD_SCALE[0]} stopOpacity={0.45} />
            <stop offset="100%" stopColor={GOLD_SCALE[0]} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
        <XAxis dataKey="order_year_month" tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <Tooltip content={<ChartTooltip valueLabel="orders" />} />
        <Area type="monotone" dataKey="order_count" stroke={GOLD_SCALE[0]} strokeWidth={2} fill="url(#orders-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
