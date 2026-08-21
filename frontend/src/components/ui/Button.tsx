import type { MouseEventHandler, ReactNode } from "react";
import { Link } from "react-router-dom";

export type ButtonVariant = "primary" | "premium" | "secondary" | "ghost" | "destructive";

/** Attributes shared by all three render targets (button / a / react-router Link). */
interface SharedTargetProps {
  id?: string;
  title?: string;
  tabIndex?: number;
  onClick?: MouseEventHandler;
  onFocus?: React.FocusEventHandler;
  onBlur?: React.FocusEventHandler;
  target?: string;
  rel?: string;
  autoFocus?: boolean;
  "aria-label"?: string;
  "aria-describedby"?: string;
  "aria-controls"?: string;
  "aria-expanded"?: boolean;
  "aria-haspopup"?: boolean | "dialog" | "menu" | "listbox" | "tree" | "grid";
  "data-testid"?: string;
}

interface BaseButtonProps extends SharedTargetProps {
  variant?: ButtonVariant;
  /** Renders the button visually disabled/inert and unclickable (still focusable, per WCAG). */
  disabled?: boolean;
  /** Shows a spinner in place of the icon and swaps the visible label for `loadingLabel`,
   * announced to assistive tech via an `aria-live` region -- the button stays disabled while true. */
  loading?: boolean;
  loadingLabel?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  fullWidth?: boolean;
  className?: string;
  children?: ReactNode;
}

interface NativeButtonExtra {
  href?: undefined;
  to?: undefined;
  type?: "button" | "submit" | "reset";
  /** Spread onto the underlying <button> untouched -- covers any native
   * attribute (form, name, value, ...) this list doesn't name explicitly. */
  buttonProps?: Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, keyof SharedTargetProps | "type" | "disabled" | "className" | "children">;
}
interface AnchorExtra {
  href: string;
  to?: undefined;
  type?: undefined;
  buttonProps?: undefined;
}
interface RouterLinkExtra {
  to: string;
  href?: undefined;
  type?: undefined;
  buttonProps?: undefined;
}

export type ButtonProps = BaseButtonProps & (NativeButtonExtra | AnchorExtra | RouterLinkExtra);

function buildClassName(variant: ButtonVariant, fullWidth: boolean, loading: boolean, disabled: boolean, className?: string) {
  return [
    "bsr-btn",
    `bsr-btn--${variant}`,
    fullWidth && "bsr-btn--full",
    loading && "bsr-btn--loading",
    disabled && "bsr-btn--disabled",
    className,
  ]
    .filter(Boolean)
    .join(" ");
}

function ButtonContent({
  loading,
  loadingLabel,
  leftIcon,
  rightIcon,
  children,
}: Pick<BaseButtonProps, "loading" | "loadingLabel" | "leftIcon" | "rightIcon" | "children">) {
  return (
    <>
      {loading && <span className="bsr-btn__spinner" aria-hidden="true" />}
      {!loading && leftIcon && (
        <span className="bsr-btn__icon" aria-hidden="true">
          {leftIcon}
        </span>
      )}
      <span className="bsr-btn__label">{children}</span>
      {!loading && rightIcon && (
        <span className="bsr-btn__icon" aria-hidden="true">
          {rightIcon}
        </span>
      )}
      {loading && (
        <span className="bsr-visually-hidden" role="status" aria-live="polite">
          {loadingLabel ?? "Loading"}
        </span>
      )}
    </>
  );
}

/**
 * Baseera's single reusable button. Renders a native <button> by default;
 * pass `to` for an internal react-router link or `href` for a plain anchor
 * styled identically -- e.g. a premium CTA that is really a navigation link.
 * Link/anchor forms ignore `loading`/`disabled` for the click itself (there's
 * no native disabled state for <a>) but still render the visual + aria state.
 */
export function Button(props: ButtonProps) {
  const {
    variant = "primary",
    disabled = false,
    loading = false,
    loadingLabel,
    leftIcon,
    rightIcon,
    fullWidth = false,
    className,
    children,
    id,
    title,
    tabIndex,
    onClick,
    onFocus,
    onBlur,
    target,
    rel,
    autoFocus,
    href,
    to,
    type,
    buttonProps,
    ...aria
  } = props;

  const isInert = disabled || loading;
  const classes = buildClassName(variant, fullWidth, loading, isInert, className);
  const content = <ButtonContent loading={loading} loadingLabel={loadingLabel} leftIcon={leftIcon} rightIcon={rightIcon}>{children}</ButtonContent>;

  if (to) {
    return (
      <Link
        to={to}
        id={id}
        title={title}
        tabIndex={isInert ? -1 : tabIndex}
        className={classes}
        onClick={isInert ? (e) => e.preventDefault() : onClick}
        onFocus={onFocus}
        onBlur={onBlur}
        target={target}
        rel={rel}
        autoFocus={autoFocus}
        aria-disabled={isInert || undefined}
        aria-busy={loading || undefined}
        {...aria}
      >
        {content}
      </Link>
    );
  }

  if (href) {
    return (
      <a
        href={isInert ? undefined : href}
        id={id}
        title={title}
        tabIndex={isInert ? -1 : tabIndex}
        className={classes}
        onClick={isInert ? (e) => e.preventDefault() : onClick}
        onFocus={onFocus}
        onBlur={onBlur}
        target={target}
        rel={rel}
        autoFocus={autoFocus}
        aria-disabled={isInert || undefined}
        aria-busy={loading || undefined}
        {...aria}
      >
        {content}
      </a>
    );
  }

  return (
    <button
      type={type ?? "button"}
      id={id}
      title={title}
      tabIndex={tabIndex}
      className={classes}
      disabled={isInert}
      aria-busy={loading || undefined}
      onClick={onClick}
      onFocus={onFocus}
      onBlur={onBlur}
      autoFocus={autoFocus}
      {...aria}
      {...buttonProps}
    >
      {content}
    </button>
  );
}
