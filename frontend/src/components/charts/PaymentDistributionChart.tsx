import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { GOLD_SCALE } from "../../utils/chartColors";
import { ChartTooltip } from "./ChartTooltip";

const LABELS: Record<string, string> = {
  credit_card: "Credit Card", boleto: "Boleto", voucher: "Voucher", debit_card: "Debit Card", not_defined: "Not Defined",
};

export function PaymentDistributionChart({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .map(([type, count]) => ({ name: LABELS[type] ?? type, count }))
    .sort((a, b) => b.count - a.count);
  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie data={rows} dataKey="count" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={95} paddingAngle={2}>
          {rows.map((row, idx) => (
            <Cell key={row.name} fill={GOLD_SCALE[idx % GOLD_SCALE.length]} stroke="var(--bg)" strokeWidth={2} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip valueLabel="orders" />} />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
