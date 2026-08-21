import type { ElementType, HTMLAttributes, ReactNode } from "react";

export interface SurfaceCardProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
  /** Adds the hover-lift used by KPI-style cards; leave off for static content. */
  interactive?: boolean;
  children?: ReactNode;
}

/**
 * Opaque elevated card for dense, data-heavy content (KPIs, tables, forms)
 * where the blur of GlassCard would hurt legibility.
 */
export function SurfaceCard({ as: Component = "div", interactive = false, className, children, ...rest }: SurfaceCardProps) {
  const classes = ["bsr-surface-card", interactive && "bsr-surface-card--interactive", className].filter(Boolean).join(" ");
  return (
    <Component className={classes} {...rest}>
      {children}
    </Component>
  );
}
