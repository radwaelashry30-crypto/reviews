import type { HTMLAttributes, ReactNode } from "react";

export interface PageContainerProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
  /** Widens the max-width for dashboard-density pages with many charts. */
  wide?: boolean;
}

/** Consistent max-width + horizontal padding wrapper for app page content. */
export function PageContainer({ wide = false, className, children, ...rest }: PageContainerProps) {
  const classes = ["bsr-page-container", wide && "bsr-page-container--wide", className].filter(Boolean).join(" ");
  return (
    <div className={classes} {...rest}>
      {children}
    </div>
  );
}
