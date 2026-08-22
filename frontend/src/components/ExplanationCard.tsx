import { LoadingState } from "./ui/LoadingState";
import type { ExplainResponse } from "../types/sentiment";

export function ExplanationCard({ result, loading }: { result: ExplainResponse | null; loading: boolean }) {
  if (loading) {
    return (
      <div>
        <div className="bsr-sentiment-card-head">
          <span className="bsr-label">Explainable AI</span>
        </div>
        <LoadingState label="Running SHAP over the model (a few seconds)…" />
      </div>
    );
  }

  if (!result) return null;

  if (!result.available) {
    return (
      <div>
        <div className="bsr-sentiment-card-head">
          <span className="bsr-label">Explainable AI</span>
        </div>
        <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
          Not available ({result.reason ?? "unknown reason"}). SHAP explanations only work with the BERT model.
        </p>
      </div>
    );
  }

  const tokens = result.top_tokens_toward_positive ?? [];
  const maxAbs = Math.max(...tokens.map((t) => Math.abs(t.shap_value)), 0.0001);

  return (
    <div>
      <div className="bsr-sentiment-card-head">
        <span className="bsr-label">Explainable AI</span>
      </div>
      <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
        Words that pushed the model's prediction toward{" "}
        <span style={{ color: "var(--bsr-positive)" }}>Positive</span> or{" "}
        <span style={{ color: "var(--bsr-negative)" }}>Negative</span>, ranked by influence (SHAP values).
      </p>
      <div className="bsr-sentiment-tokens">
        {tokens.map((t, i) => {
          const intensity = Math.abs(t.shap_value) / maxAbs;
          const isPositive = t.shap_value >= 0;
          return (
            <span
              key={`${t.token}-${i}`}
              className="bsr-sentiment-token-chip"
              style={{
                background: isPositive ? `rgba(61, 220, 151, ${0.12 + intensity * 0.45})` : `rgba(255, 102, 122, ${0.12 + intensity * 0.45})`,
                borderColor: isPositive ? "var(--bsr-positive-border)" : "var(--bsr-negative-border)",
                color: "var(--bsr-text)",
              }}
              title={`${t.shap_value >= 0 ? "+" : ""}${t.shap_value.toFixed(4)}`}
            >
              {t.token}
            </span>
          );
        })}
      </div>
    </div>
  );
}
