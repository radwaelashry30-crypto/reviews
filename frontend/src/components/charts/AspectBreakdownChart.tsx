import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AspectSummaryRow } from "../../types/sentiment";
import { CHART_AXIS, CHART_GOLD, CHART_GRID, CHART_NEGATIVE, CHART_POSITIVE } from "./batch/batchChartColors";
import { BatchChartTooltip } from "./batch/BatchChartTooltip";

function formatAspectName(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

/** 100%-stacked horizontal bars, one per aspect, showing the Positive /
 * Neutral / Negative sentiment-given-aspect split from the advanced pipeline.
 * Percentages are computed only among reviews that actually mentioned the
 * aspect (see AspectSummaryRow.mentioned_pct) -- the coverage caption below
 * makes that explicit rather than letting a rarely-discussed aspect look
 * like it has a full, confident verdict. */
export function AspectBreakdownChart({ data }: { data: AspectSummaryRow[] }) {
  const rows = data.map((row) => ({
    label: formatAspectName(row.aspect),
    Positive: row.positive_pct,
    Neutral: row.neutral_pct,
    Negative: row.negative_pct,
  }));

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(220, rows.length * 48)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 12 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: CHART_AXIS }} tickFormatter={(v) => `${v}%`} />
          <YAxis type="category" dataKey="label" width={110} tick={{ fontSize: 11, fill: CHART_AXIS }} />
          <Tooltip content={<BatchChartTooltip formatValue={(v) => `${v.toFixed(0)}%`} />} cursor={{ fill: "rgba(35, 199, 255, 0.06)" }} />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--bsr-text-muted)" }} />
          <Bar dataKey="Positive" stackId="aspect" fill={CHART_POSITIVE} />
          <Bar dataKey="Neutral" stackId="aspect" fill={CHART_GOLD} />
          <Bar dataKey="Negative" stackId="aspect" fill={CHART_NEGATIVE} radius={[0, 6, 6, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "0.4rem" }}>
        Coverage -- {data.map((row) => `${formatAspectName(row.aspect)} ${row.mentioned_pct.toFixed(0)}%`).join(" · ")} of reviews actually mention that aspect; the split above is among those only.
      </p>
    </div>
  );
}
