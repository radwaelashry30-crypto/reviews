import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, Legend } from "recharts";
import type { RfmSegmentSummaryRow } from "../../types/segmentation";

const COLORS = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd"];

export function SegmentChart({ data }: { data: RfmSegmentSummaryRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey="customer_count" nameKey="Segment" cx="50%" cy="50%" outerRadius={100} label>
          {data.map((_, idx) => (
            <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
