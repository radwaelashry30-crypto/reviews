import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { RfmSegmentSummaryRow } from "../../types/segmentation";
import { GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

export function SegmentChart({ data }: { data: RfmSegmentSummaryRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey="customer_count" nameKey="Segment" cx="50%" cy="50%" innerRadius={55} outerRadius={100} paddingAngle={2}>
          {data.map((_, idx) => (
            <Cell key={idx} fill={GOLD_SCALE[idx % GOLD_SCALE.length]} stroke="var(--bg)" strokeWidth={2} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip valueLabel="customers" />} />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
