import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

export interface SentimentDonutProps {
  positive: number;
  neutral: number;
  negative: number;
  size?: number;
}

const COLOR_VARS = ["var(--bsr-positive)", "var(--bsr-warning)", "var(--bsr-negative)"];

export function SentimentDonut({ positive, neutral, negative, size = 160 }: SentimentDonutProps) {
  const rows = [
    { name: "Positive", value: positive },
    { name: "Neutral", value: neutral },
    { name: "Negative", value: negative },
  ];
  return (
    <ResponsiveContainer width="100%" height={size}>
      <PieChart>
        <Pie data={rows} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={size * 0.32} outerRadius={size * 0.46} paddingAngle={3} strokeWidth={0}>
          {rows.map((row, idx) => (
            <Cell key={row.name} fill={COLOR_VARS[idx]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "var(--bsr-elevated)", border: "1px solid var(--bsr-border-strong)", borderRadius: 10, fontSize: 12, color: "var(--bsr-text)" }}
          formatter={(value: number, name: string) => [`${value}%`, name]}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
