import type { AspectsResult } from "../types/sentiment";

const SENTIMENT_COLOR: Record<string, string> = {
  Positive: "var(--positive)",
  Negative: "var(--negative)",
  Neutral: "var(--text-faint)",
  "Not mentioned": "var(--text-faint)",
  UNKNOWN: "var(--text-faint)",
};

export function AspectsBreakdown({ result }: { result: AspectsResult }) {
  if (!result.available) {
    return (
      <div className="aspects-card aspects-unavailable">
        <span className="eyebrow">Task 3 · Why customers feel this way</span>
        <p className="limitations-note">
          Aspect analysis isn't loaded on this deployment ({result.reason ?? "unavailable"}). It runs fully
          when the API is started locally with <code>ALLOW_EXTERNAL_MODEL_DOWNLOADS=true</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="aspects-card">
      <span className="eyebrow">Task 3 · Why customers feel this way</span>
      <div className="aspects-list">
        {result.aspects?.map((a) => (
          <div className="aspect-row" key={a.aspect}>
            <span className="aspect-name">{a.aspect}</span>
            <div className="prob-bar-track aspect-track">
              <div
                className="prob-bar-fill"
                style={{ width: `${a.confidence * 100}%`, background: SENTIMENT_COLOR[a.sentiment] ?? "var(--text-faint)" }}
              />
            </div>
            <span
              className="aspect-sentiment"
              style={{ color: SENTIMENT_COLOR[a.sentiment], fontStyle: a.sentiment === "Not mentioned" ? "italic" : "normal", opacity: a.sentiment === "Not mentioned" ? 0.7 : 1 }}
            >
              {a.sentiment}
            </span>
          </div>
        ))}
      </div>
      <p className="limitations-note">{result.methodology_note}</p>
    </div>
  );
}
