import type { ApiClientError } from "../types/api";

export function ErrorState({ error }: { error: ApiClientError | Error | null }) {
  if (!error) return null;
  const message = "message" in error ? error.message : "An unexpected error occurred.";
  const code = "code" in error ? (error as ApiClientError).code : undefined;
  return (
    <div className="state state-error">
      <strong>{code ?? "ERROR"}</strong>: {message}
    </div>
  );
}
