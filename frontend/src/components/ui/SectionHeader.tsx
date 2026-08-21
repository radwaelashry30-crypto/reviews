import type { ReactNode } from "react";

export interface SectionHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

/** Eyebrow + heading + description, with an optional trailing action slot (e.g. a Button). */
export function SectionHeader({ eyebrow, title, description, action, className }: SectionHeaderProps) {
  return (
    <div className={className ? `bsr-section-header ${className}` : "bsr-section-header"}>
      <div className="bsr-section-header__text">
        {eyebrow && <span className="bsr-label bsr-section-header__eyebrow">{eyebrow}</span>}
        <h2 className="bsr-h2">{title}</h2>
        {description && <p className="bsr-body bsr-section-header__description">{description}</p>}
      </div>
      {action && <div className="bsr-section-header__action">{action}</div>}
    </div>
  );
}
