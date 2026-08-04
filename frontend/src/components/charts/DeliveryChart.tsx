import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface StatePerformanceRow {
  customer_state_name: string;
  late_pct: number;
  [key: string]: unknown;
}

export function DeliveryChart({ data }: { data: StatePerformanceRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="customer_state_name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 11 }} unit="%" />
        <Tooltip />
        <Bar dataKey="late_pct" fill="#d62728" />
      </BarChart>
    </ResponsiveContainer>
  );
}
