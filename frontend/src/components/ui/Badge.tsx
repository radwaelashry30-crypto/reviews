import type { ReactNode } from "react";

export type StatusTone = "positive" | "negative" | "warning" | "neutral" | "blue" | "gold";

export interface StatusPillProps {
  tone?: StatusTone;
  children: ReactNode;
  /** Shows the small status dot; off for a plain label pill. */
  dot?: boolean;
  className?: string;
}

/** Semantic status indicator -- e.g. Positive / Negative / Needs review. */
export function StatusPill({ tone = "neutral", children, dot = true, className }: StatusPillProps) {
  const classes = ["bsr-status-pill", `bsr-status-pill--${tone}`, className].filter(Boolean).join(" ");
  return (
    <span className={classes}>
      {dot && <span className="bsr-status-pill__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

export interface BadgeProps {
  children: ReactNode;
  tone?: StatusTone;
  className?: string;
}

/** Plain label pill (no dot) -- counts, tags, categories. */
export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  return <StatusPill tone={tone} dot={false} className={className}>{children}</StatusPill>;
}
