import type { ElementType, HTMLAttributes, ReactNode } from "react";

export type GlassCardGlow = "none" | "blue" | "gold";

export interface GlassCardProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
  glow?: GlassCardGlow;
  children?: ReactNode;
}

/**
 * Translucent, blurred panel over the dark navy ground -- the brief's
 * "elegant glassmorphism". Use for content that sits above imagery/video
 * (hero cards, floating panels). For dense data (tables, KPI grids) prefer
 * SurfaceCard, which trades the blur for guaranteed text legibility.
 */
export function GlassCard({ as: Component = "div", glow = "none", className, children, ...rest }: GlassCardProps) {
  const classes = ["bsr-glass-card", glow !== "none" && `bsr-glass-card--glow-${glow}`, className].filter(Boolean).join(" ");
  return (
    <Component className={classes} {...rest}>
      {children}
    </Component>
  );
}
