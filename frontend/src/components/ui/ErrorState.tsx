import type { ReactNode } from "react";
import { Button } from "./Button";

export interface ErrorStateProps {
  title?: string;
  message: string;
  code?: string;
  onRetry?: () => void;
  icon?: ReactNode;
}

/**
 * Design-system error placeholder. Deliberately generic (a plain message +
 * optional code), unlike the existing app-level `ErrorState`, which knows
 * how to unpack an `ApiClientError`. Pages keep using that one until Phase 3
 * migrates them onto this design system; format the message before passing
 * it in here.
 */
export function ErrorState({ title = "Something went wrong", message, code, onRetry, icon }: ErrorStateProps) {
  return (
    <div className="bsr-error-state" role="alert">
      {icon && (
        <span className="bsr-error-state__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <p className="bsr-h5">{title}</p>
      <p className="bsr-sm">
        {code && <span className="bsr-mono bsr-error-state__code">{code}</span>}
        {message}
      </p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} className="bsr-error-state__action">
          Try again
        </Button>
      )}
    </div>
  );
}
