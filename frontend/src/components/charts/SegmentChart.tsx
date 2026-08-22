import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { RfmSegmentSummaryRow } from "../../types/segmentation";
import { GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

export interface SegmentChartProps {
  data: RfmSegmentSummaryRow[];
  /** Optional override for the slice palette -- defaults to the legacy
   * `GOLD_SCALE` so the Customers page (which doesn't pass this) keeps its
   * current look until its own redesign phase. The dashboard passes the
   * Baseera `BLUE_SCALE` instead. */
  colors?: string[];
}

export function SegmentChart({ data, colors }: SegmentChartProps) {
  const palette = colors && colors.length > 0 ? colors : GOLD_SCALE;
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey="customer_count" nameKey="Segment" cx="50%" cy="50%" innerRadius={55} outerRadius={100} paddingAngle={2}>
          {data.map((_, idx) => (
            <Cell key={idx} fill={palette[idx % palette.length]} stroke="var(--bg)" strokeWidth={2} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip valueLabel="customers" />} />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
