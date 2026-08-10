import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_AXIS, CHART_GRID, CHART_NEGATIVE, CHART_POSITIVE, GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

// 1-2 stars read as negative, 3 neutral (gold), 4-5 positive -- ties the chart back to the same
// sentiment vocabulary used across the rest of the product instead of an arbitrary color ramp.
const SCORE_COLOR: Record<string, string> = {
  "1": CHART_NEGATIVE, "2": CHART_NEGATIVE, "3": GOLD_SCALE[3], "4": CHART_POSITIVE, "5": CHART_POSITIVE,
};

export function ReviewDistributionChart({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .map(([score, count]) => ({ score: `${score} stars`, count, key: score }))
    .sort((a, b) => a.score.localeCompare(b.score));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
        <XAxis dataKey="score" tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <Tooltip content={<ChartTooltip valueLabel="reviews" />} cursor={{ fill: "rgba(201, 153, 46, 0.06)" }} />
        <Bar dataKey="count" radius={[6, 6, 0, 0]}>
          {rows.map((row) => (
            <Cell key={row.key} fill={SCORE_COLOR[row.key] ?? GOLD_SCALE[0]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
