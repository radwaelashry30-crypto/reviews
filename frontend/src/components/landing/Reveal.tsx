import type { ElementType, HTMLAttributes, ReactNode, Ref } from "react";
import { useInView } from "./hooks/useInView";

export interface RevealProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
  children?: ReactNode;
  delayMs?: number;
}

/** Fades + lifts content into place the first time it scrolls into view. A
 * no-op (renders immediately, no animation) under prefers-reduced-motion,
 * handled globally by the `*` transition-duration override in tokens.css. */
export function Reveal({ as: Component = "div", children, delayMs = 0, className, style, ...rest }: RevealProps) {
  const { ref, inView } = useInView<HTMLElement>();
  return (
    <Component
      ref={ref as Ref<HTMLElement>}
      className={["bsr-reveal", inView && "bsr-reveal--visible", className].filter(Boolean).join(" ")}
      style={{ transitionDelay: inView ? `${delayMs}ms` : "0ms", ...style }}
      {...rest}
    >
      {children}
    </Component>
  );
}
