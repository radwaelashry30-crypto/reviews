import type { ReactNode, MouseEventHandler } from "react";

export type IconButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
export type IconButtonSize = "sm" | "md";

export interface IconButtonProps {
  icon: ReactNode;
  /** Required -- an icon-only control has no visible text, so this is its only accessible name. */
  "aria-label": string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  type?: "button" | "submit" | "reset";
  id?: string;
  title?: string;
  "data-testid"?: string;
}

/**
 * The icon-only member of the button family (section 5 of the design
 * foundation asks for it as its own primitive rather than a Button prop).
 * Shares the same visual states/tokens as Button but is always a square
 * hit target sized for a single glyph.
 */
export function IconButton({
  icon,
  variant = "secondary",
  size = "md",
  disabled = false,
  loading = false,
  className,
  onClick,
  type = "button",
  id,
  title,
  ...rest
}: IconButtonProps) {
  const isInert = disabled || loading;
  const classes = [
    "bsr-icon-btn",
    `bsr-icon-btn--${variant}`,
    `bsr-icon-btn--${size}`,
    loading && "bsr-icon-btn--loading",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type={type}
      id={id}
      title={title}
      className={classes}
      disabled={isInert}
      aria-busy={loading || undefined}
      onClick={onClick}
      {...rest}
    >
      {loading ? <span className="bsr-btn__spinner" aria-hidden="true" /> : <span className="bsr-icon-btn__glyph" aria-hidden="true">{icon}</span>}
    </button>
  );
}
