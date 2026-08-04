import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function ReviewDistributionChart({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .map(([score, count]) => ({ score: `${score} stars`, count }))
    .sort((a, b) => a.score.localeCompare(b.score));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="score" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey="count" fill="#ff7f0e" />
      </BarChart>
    </ResponsiveContainer>
  );
}
