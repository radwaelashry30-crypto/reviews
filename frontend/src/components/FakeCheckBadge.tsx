import type { FakeCheckResult } from "../types/sentiment";

export function FakeCheckBadge({ result }: { result: FakeCheckResult | null }) {
  if (result === null) return null;

  if (!result.available) {
    return (
      <div className="fake-check-card fake-check-unavailable">
        <span className="eyebrow">Task 2 · Authenticity check</span>
        <p className="limitations-note">
          Not loaded on this deployment ({result.reason ?? "unavailable"}). This module is off by default --
          see <code>ENABLE_FAKE_REVIEW_MODULE</code> in the deployment config.
        </p>
      </div>
    );
  }

  // A verdict that flipped under meaning-preserving rewording is not
  // evidence of anything -- don't present it with the same weight as a
  // stable one. This is the actual enforcement of `reliable`, not just a
  // caption next to an unconditionally-shown verdict.
  const isUnreliable = result.stability_checked && result.reliable === false;

  return (
    <div className="fake-check-card fake-check-exploratory">
      <span className="eyebrow">Task 2 · Authenticity check (exploratory, unreliable)</span>
      {isUnreliable ? (
        <div className="fake-check-verdict fake-check-verdict-suppressed">
          Verdict withheld -- flipped under meaning-preserving rewording of this same review, so it isn't a usable signal.
        </div>
      ) : (
        <div className="fake-check-verdict">
          {result.is_fake ? "Model output: LABEL_1 (assumed “fake”)" : "Model output: LABEL_0 (assumed “real”)"}
        </div>
      )}
      {result.stability_checked && (
        <div className={`fake-check-stability ${result.reliable ? "stable" : "unstable"}`}>
          {result.reliable ? "✓ Stable under rewording" : "⚠ Unstable under rewording"}
          {typeof result.verdict_spread === "number" && ` (spread: ${(result.verdict_spread * 100).toFixed(0)}%)`}
        </div>
      )}
      {result.reliability_note && <p className="limitations-note">{result.reliability_note}</p>}
      <p className="limitations-note">{result.disclaimer}</p>
    </div>
  );
}
