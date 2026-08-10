import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { CHART_NEGATIVE, CHART_POSITIVE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

export function SentimentSplitChart({ nPositive, nNegative }: { nPositive: number; nNegative: number }) {
  const rows = [
    { name: "Positive", value: nPositive, color: CHART_POSITIVE },
    { name: "Negative", value: nNegative, color: CHART_NEGATIVE },
  ];
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={rows} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3}>
          {rows.map((row) => (
            <Cell key={row.name} fill={row.color} stroke="var(--bg)" strokeWidth={2} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip valueLabel="reviews" />} />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
