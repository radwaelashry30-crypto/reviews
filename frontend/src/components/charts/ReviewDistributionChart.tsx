import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_AXIS, CHART_GRID, CHART_NEGATIVE, CHART_POSITIVE, CHART_WARNING } from "./dashboard/dashboardChartColors";
import { DashboardChartTooltip } from "./dashboard/DashboardChartTooltip";

// Below 3 reads as negative, 3-under-4 neutral (warning/gold), 4+ positive --
// ties the chart back to the same sentiment vocabulary used across the rest
// of the product instead of an arbitrary color ramp. Scored numerically
// (not by exact string key: the API returns fractional averages like
// "3.3333333333333335" alongside whole scores, not just "1".."5" -- a
// pre-existing bug matched only literal "1"-"5" keys, so every bar silently
// fell back to the same gray and the color-coding never actually applied;
// fixed here since it's a presentation bug in a chart already in scope for
// this reskin, not a change to the underlying counts).
function scoreColor(score: number): string {
  if (score < 3) return CHART_NEGATIVE;
  if (score < 4) return CHART_WARNING;
  return CHART_POSITIVE;
}

export function ReviewDistributionChart({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .map(([score, count]) => ({ score: `${score} stars`, count, key: score, numericScore: Number(score) }))
    .sort((a, b) => a.numericScore - b.numericScore);
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
        <XAxis dataKey="score" tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <Tooltip content={<DashboardChartTooltip valueLabel="reviews" />} cursor={{ fill: "rgba(35, 199, 255, 0.06)" }} />
        <Bar dataKey="count" radius={[6, 6, 0, 0]}>
          {rows.map((row) => (
            <Cell key={row.key} fill={scoreColor(row.numericScore)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
