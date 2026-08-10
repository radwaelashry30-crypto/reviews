import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonthlyRevenuePoint } from "../../types/analytics";
import { CHART_AXIS, CHART_GRID, GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

export function RevenueTrendChart({ data }: { data: MonthlyRevenuePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="revenue-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={GOLD_SCALE[1]} stopOpacity={0.5} />
            <stop offset="100%" stopColor={GOLD_SCALE[1]} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
        <XAxis dataKey="order_year_month" tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <Tooltip content={<ChartTooltip formatValue={(v) => `R$${v.toLocaleString()}`} />} />
        <Area type="monotone" dataKey="total_payment_value" stroke={GOLD_SCALE[1]} strokeWidth={2} fill="url(#revenue-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
