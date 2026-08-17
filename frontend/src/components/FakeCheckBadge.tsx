import type { FakeCheckResult } from "../types/sentiment";

export function FakeCheckBadge({ result }: { result: FakeCheckResult | null }) {
  if (result === null) return null;

  if (!result.available) {
    return (
      <div className="fake-check-card fake-check-unavailable">
        <span className="eyebrow">Task 2 · Authenticity check</span>
        <p className="limitations-note">
          Not loaded on this deployment ({result.reason ?? "unavailable"}). Runs locally with{" "}
          <code>ALLOW_EXTERNAL_MODEL_DOWNLOADS=true</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="fake-check-card fake-check-exploratory">
      <span className="eyebrow">Task 2 · Authenticity check (exploratory, unreliable)</span>
      <div className="fake-check-verdict">
        {result.is_fake ? "Model output: LABEL_1 (assumed “fake”)" : "Model output: LABEL_0 (assumed “real”)"}
      </div>
      <p className="limitations-note">{result.disclaimer}</p>
    </div>
  );
}
