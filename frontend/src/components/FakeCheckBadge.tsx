import { useId, useState } from "react";
import { StatusPill } from "./ui/Badge";
import { Button } from "./ui/Button";
import type { FakeCheckResult } from "../types/sentiment";

const DOMAIN_SHIFT_CAUTION =
  "Trained on hotel reviews, applied here to e-commerce reviews -- a real domain shift, not separately measured.";

export function FakeCheckBadge({ result }: { result: FakeCheckResult | null }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();

  if (result === null) return null;

  if (!result.available) {
    return (
      <div>
        <div className="bsr-sentiment-card-head">
          <span className="bsr-label">Authenticity signal</span>
        </div>
        <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
          Not loaded on this deployment ({result.reason ?? "unavailable"}). This experimental module is off by default -- see{" "}
          <code>ENABLE_FAKE_REVIEW_MODULE</code> in the deployment config.
        </p>
      </div>
    );
  }

  const isUncertain = result.verdict === "UNCERTAIN";

  return (
    <div className="bsr-sentiment-authenticity">
      <div className="bsr-sentiment-card-head">
        <span className="bsr-label">Experimental authenticity signal</span>
      </div>

      {isUncertain ? (
        <div className="bsr-sentiment-authenticity__verdict">
          <StatusPill tone="warning">Uncertain</StatusPill>
          <span className="bsr-sm">This review's score is close to the model's decision boundary, so no confident signal is given.</span>
        </div>
      ) : (
        <div className="bsr-sentiment-authenticity__verdict">
          <StatusPill tone={result.is_fake ? "warning" : "positive"}>
            {result.is_fake ? "Elevated experimental signal" : "No elevated experimental signal"}
          </StatusPill>
        </div>
      )}

      {typeof result.fake_probability === "number" && (
        <p className="bsr-sm" style={{ color: "var(--bsr-text-muted)" }}>
          Experimental fake-review probability: <strong style={{ color: "var(--bsr-text)" }}>{(result.fake_probability * 100).toFixed(0)}%</strong>
        </p>
      )}

      {result.is_fake && !isUncertain && (
        <p className="bsr-sm" style={{ color: "var(--bsr-warning)" }}>
          This is not proof that the review is fake.
        </p>
      )}

      <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
        {DOMAIN_SHIFT_CAUTION}
      </p>

      <Button
        type="button"
        variant="ghost"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-controls={detailsId}
      >
        {expanded ? "Hide technical details" : "Why this result is uncertain"}
      </Button>

      {expanded && (
        <div id={detailsId} className="bsr-sentiment-authenticity__details">
          <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
            {result.disclaimer ??
              "This is a statistical screening estimate, not a verified fraud finding -- it should never be treated as an accusation against the reviewer."}
          </p>
          {result.model && (
            <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
              Model: <code>{result.model}</code>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
