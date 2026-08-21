import { StatusPill } from "./Badge";

export type DemoDataKind = "demo" | "historical";

const LABELS: Record<DemoDataKind, string> = {
  demo: "Demonstration data",
  historical: "Historical dataset (2017–2018)",
};

export interface DemoDataBadgeProps {
  kind?: DemoDataKind;
  label?: string;
  className?: string;
}

/**
 * Required per product decision: never let a demo review, sample metric, or
 * the static Olist dataset read as live production data. Drop this next to
 * anything that isn't a real-time figure.
 */
export function DemoDataBadge({ kind = "demo", label, className }: DemoDataBadgeProps) {
  return (
    <StatusPill tone="gold" dot={false} className={className ? `bsr-demo-badge ${className}` : "bsr-demo-badge"}>
      {label ?? LABELS[kind]}
    </StatusPill>
  );
}
