import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FileRowResult } from "../../types/sentiment";
import { CHART_AXIS, CHART_GRID, GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

const BUCKETS = [
  { label: "50-60%", min: 0.5, max: 0.6 },
  { label: "60-70%", min: 0.6, max: 0.7 },
  { label: "70-80%", min: 0.7, max: 0.8 },
  { label: "80-90%", min: 0.8, max: 0.9 },
  { label: "90-100%", min: 0.9, max: 1.01 },
];

export function ConfidenceHistogramChart({ results }: { results: FileRowResult[] }) {
  const rows = BUCKETS.map((b) => ({
    label: b.label,
    count: results.filter((r) => r.confidence !== undefined && r.confidence >= b.min && r.confidence < b.max).length,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: CHART_AXIS }} />
        <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} allowDecimals={false} />
        <Tooltip content={<ChartTooltip valueLabel="reviews" />} cursor={{ fill: "rgba(201, 153, 46, 0.06)" }} />
        <Bar dataKey="count" fill={GOLD_SCALE[0]} radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
