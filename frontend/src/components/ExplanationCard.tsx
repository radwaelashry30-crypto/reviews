import type { ExplainResponse } from "../types/sentiment";

export function ExplanationCard({ result, loading }: { result: ExplainResponse | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="explanation-card">
        <span className="eyebrow">Explainable AI</span>
        <p className="limitations-note">Running SHAP over the model (a few seconds)...</p>
      </div>
    );
  }

  if (!result) return null;

  if (!result.available) {
    return (
      <div className="explanation-card">
        <span className="eyebrow">Explainable AI</span>
        <p className="limitations-note">
          Not available ({result.reason ?? "unknown reason"}). SHAP explanations only work with the BERT model.
        </p>
      </div>
    );
  }

  const tokens = result.top_tokens_toward_positive ?? [];
  const maxAbs = Math.max(...tokens.map((t) => Math.abs(t.shap_value)), 0.0001);

  return (
    <div className="explanation-card">
      <span className="eyebrow">Explainable AI</span>
      <p className="limitations-note" style={{ marginTop: "0.5rem" }}>
        Words that pushed the model's prediction toward <span style={{ color: "var(--positive)" }}>Positive</span> or{" "}
        <span style={{ color: "var(--negative)" }}>Negative</span>, ranked by influence (SHAP values).
      </p>
      <div className="token-chip-list">
        {tokens.map((t, i) => {
          const intensity = Math.abs(t.shap_value) / maxAbs;
          const isPositive = t.shap_value >= 0;
          return (
            <span
              key={`${t.token}-${i}`}
              className="token-chip"
              style={{
                background: isPositive ? `rgba(92, 179, 122, ${0.15 + intensity * 0.55})` : `rgba(217, 112, 95, ${0.15 + intensity * 0.55})`,
                borderColor: isPositive ? "var(--positive-border)" : "var(--negative-border)",
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
