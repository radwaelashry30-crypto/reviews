import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TimeTrendPoint } from "../../types/sentiment";
import { CHART_AXIS, CHART_GRID, CHART_POSITIVE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

/** Weekly Positive-rate trend from the uploaded file's own date column
 * (file_batch_service._build_time_trend on the backend). Only rendered when
 * time_trend.available is true. */
export function SentimentTrendChart({ data }: { data: TimeTrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="sentiment-trend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_POSITIVE} stopOpacity={0.4} />
            <stop offset="100%" stopColor={CHART_POSITIVE} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
        <XAxis dataKey="period" tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: CHART_AXIS }} tickFormatter={(v) => `${v}%`} />
        <Tooltip content={<ChartTooltip valueLabel="% positive" formatValue={(v) => v.toFixed(1)} />} />
        <Area type="monotone" dataKey="positive_pct" stroke={CHART_POSITIVE} strokeWidth={2} fill="url(#sentiment-trend-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
