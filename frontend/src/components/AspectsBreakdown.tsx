import { EmptyState } from "./ui/EmptyState";
import type { AspectsResult } from "../types/sentiment";

const SENTIMENT_COLOR: Record<string, string> = {
  Positive: "var(--bsr-positive)",
  Negative: "var(--bsr-negative)",
  Neutral: "var(--bsr-text-faint)",
  "Not mentioned": "var(--bsr-text-faint)",
  UNKNOWN: "var(--bsr-text-faint)",
};

export function AspectsBreakdown({ result }: { result: AspectsResult }) {
  if (!result.available) {
    return (
      <div>
        <div className="bsr-sentiment-card-head">
          <span className="bsr-label">Aspect breakdown</span>
        </div>
        <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
          Aspect analysis is unavailable in the current deployment. The sentiment result above is still available.
        </p>
      </div>
    );
  }

  const aspects = result.aspects ?? [];

  return (
    <div>
      <div className="bsr-sentiment-card-head">
        <span className="bsr-label">Aspect breakdown</span>
      </div>

      {aspects.length === 0 ? (
        <EmptyState title="No aspect signals detected" description="This review didn't contain language the model could confidently tie to a specific aspect." />
      ) : (
        <div className="bsr-sentiment-aspects">
          {aspects.map((a) => {
            const isUnrated = a.sentiment === "Not mentioned" || a.sentiment === "UNKNOWN";
            return (
              <div className="bsr-sentiment-aspect-row" key={a.aspect}>
                <span className="bsr-sentiment-aspect-row__name">{a.aspect}</span>
                <div className="bsr-sentiment-aspect-track">
                  {!isUnrated && (
                    <div
                      className="bsr-sentiment-aspect-fill"
                      style={{ width: `${a.confidence * 100}%`, background: SENTIMENT_COLOR[a.sentiment] ?? "var(--bsr-text-faint)" }}
                    />
                  )}
                </div>
                <span
                  className="bsr-sm bsr-sentiment-aspect-row__value"
                  style={{ color: SENTIMENT_COLOR[a.sentiment] ?? "var(--bsr-text-faint)", fontStyle: isUnrated ? "italic" : "normal" }}
                >
                  {a.sentiment}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {result.methodology_note && (
        <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "var(--bsr-space-3)" }}>
          {result.methodology_note}
        </p>
      )}
    </div>
  );
}
