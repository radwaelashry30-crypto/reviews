import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TrendPoint } from "../demoData";

export interface MiniAreaChartProps {
  data: TrendPoint[];
  height?: number;
  showAxes?: boolean;
}

/**
 * Small on-brand trend chart for the landing page. Deliberately not a reuse
 * of `components/charts/*` -- those import fixed colors from
 * `utils/chartColors.ts` tuned to the legacy brown/gold theme, which would
 * fight the cinematic navy/blue direction here and can't be safely
 * repointed without touching styling shared by the existing app pages
 * (out of scope for Phase 2). This uses the same library (recharts, already
 * a dependency) and reads colors straight from the Phase 1 `--bsr-*` tokens.
 */
export function MiniAreaChart({ data, height = 120, showAxes = false }: MiniAreaChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: showAxes ? 0 : -24 }}>
        <defs>
          <linearGradient id="bsr-trend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--bsr-blue)" stopOpacity={0.5} />
            <stop offset="100%" stopColor="var(--bsr-blue)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        {showAxes && (
          <>
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--bsr-text-muted)" }} axisLine={false} tickLine={false} />
            <YAxis hide domain={[0, 100]} />
          </>
        )}
        {!showAxes && <YAxis hide domain={[0, 100]} />}
        <Tooltip
          cursor={{ stroke: "var(--bsr-border-strong)" }}
          contentStyle={{ background: "var(--bsr-elevated)", border: "1px solid var(--bsr-border-strong)", borderRadius: 10, fontSize: 12, color: "var(--bsr-text)" }}
          labelStyle={{ color: "var(--bsr-text-faint)" }}
          formatter={(value: number) => [`${value}%`, "Positive"]}
        />
        <Area type="monotone" dataKey="positivePct" stroke="var(--bsr-blue)" strokeWidth={2} fill="url(#bsr-trend-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
