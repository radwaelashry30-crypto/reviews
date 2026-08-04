import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonthlyOrderPoint } from "../../types/analytics";

export function OrdersTrendChart({ data }: { data: MonthlyOrderPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="order_year_month" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Line type="monotone" dataKey="order_count" stroke="#1f77b4" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
