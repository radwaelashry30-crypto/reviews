import type { ReactNode } from "react";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Nothing-to-show placeholder -- distinct from ErrorState (nothing went wrong, there's just no data yet). */
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="bsr-empty-state">
      {icon && (
        <span className="bsr-empty-state__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <p className="bsr-h5">{title}</p>
      {description && <p className="bsr-sm">{description}</p>}
      {action && <div className="bsr-empty-state__action">{action}</div>}
    </div>
  );
}
