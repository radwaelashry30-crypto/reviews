import type { ReactNode } from "react";
import { ErrorState } from "../ui/ErrorState";
import { LoadingState } from "../ui/LoadingState";
import { EmptyState } from "../ui/EmptyState";
import type { ApiClientError } from "../../types/api";

export interface ChartPanelStateProps {
  loading: boolean;
  error: ApiClientError | Error | null;
  isEmpty?: boolean;
  loadingLabel?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  children: ReactNode;
}

/**
 * The loading/error/empty/data switch every chart panel on the dashboard
 * needs, wired to Phase 1's `ui/` presentational components instead of the
 * legacy app-level LoadingState/ErrorState (those stay as they are --
 * they're still used by every other, not-yet-reskinned page). Purely
 * presentational: it reads the same `{ data, loading, error }` shape
 * `useAsync` already returns and never touches how that data is fetched.
 *
 * No retry action is wired up because none of the existing analytics hooks
 * expose a refetch function -- adding one would be a data-handling change,
 * out of scope for a visual reskin (flagged in the phase report instead).
 */
export function ChartPanelState({ loading, error, isEmpty, loadingLabel = "Loading…", emptyTitle = "No data yet", emptyDescription, children }: ChartPanelStateProps) {
  if (loading) return <LoadingState label={loadingLabel} />;
  if (error) {
    const code = "code" in error ? (error as ApiClientError).code : undefined;
    return <ErrorState code={code} message={error.message || "An unexpected error occurred."} />;
  }
  if (isEmpty) return <EmptyState title={emptyTitle} description={emptyDescription} />;
  return <>{children}</>;
}
