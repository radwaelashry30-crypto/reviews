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
    <div className={`fake-check-card ${result.is_fake ? "flagged" : "clear"}`}>
      <span className="eyebrow">Task 2 · Authenticity check</span>
      <div className="fake-check-verdict">
        {result.is_fake ? "⚠ Flagged as possibly fake" : "✓ No fake-review signal detected"}
      </div>
      <p className="limitations-note">{result.disclaimer}</p>
    </div>
  );
}
