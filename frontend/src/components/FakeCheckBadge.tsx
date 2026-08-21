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

  const isUncertain = result.verdict === "UNCERTAIN";

  return (
    <div className="fake-check-card fake-check-validated">
      <span className="eyebrow">Task 2 · Authenticity check</span>
      {isUncertain ? (
        <div className="fake-check-verdict fake-check-verdict-uncertain">
          Uncertain -- this review's score is close to the model's decision boundary, so no confident verdict is given.
        </div>
      ) : (
        <div className={`fake-check-verdict ${result.is_fake ? "verdict-fake" : "verdict-real"}`}>
          {result.is_fake ? "Likely deceptive" : "Likely genuine"}
          {typeof result.fake_probability === "number" && ` (${(result.fake_probability * 100).toFixed(0)}% fake-probability)`}
        </div>
      )}
      <p className="limitations-note">{result.disclaimer}</p>
    </div>
  );
}
