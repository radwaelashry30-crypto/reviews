export interface LoadingStateProps {
  label?: string;
  /** Centers in a tall block instead of sitting inline -- use for a whole-page/section load. */
  fullBleed?: boolean;
}

/** Design-system loading indicator: spinner + label, announced via aria-live. */
export function LoadingState({ label = "Loading…", fullBleed = false }: LoadingStateProps) {
  return (
    <div className={fullBleed ? "bsr-loading-state bsr-loading-state--full" : "bsr-loading-state"} role="status" aria-live="polite">
      <span className="bsr-btn__spinner bsr-loading-state__spinner" aria-hidden="true" />
      <span className="bsr-sm">{label}</span>
    </div>
  );
}
