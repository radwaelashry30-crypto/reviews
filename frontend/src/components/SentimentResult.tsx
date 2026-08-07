import type { SentimentPrediction } from "../types/sentiment";
import { formatPercent } from "../utils/formatters";

export function SentimentResult({ result }: { result: SentimentPrediction }) {
  const isPositive = result.label === "Positive";
  return (
    <div className={`sentiment-result ${isPositive ? "positive" : "negative"}`}>
      <div className="sentiment-result-label">
        {isPositive ? "▲" : "▼"} {result.label}
      </div>
      <div className="sentiment-result-confidence">
        {formatPercent(result.confidence * 100)} confidence
      </div>

      <div className="sentiment-result-probs">
        <div className="prob-bar-row">
          <span style={{ width: 56 }}>Positive</span>
          <div className="prob-bar-track">
            <div className="prob-bar-fill positive" style={{ width: `${result.probability_positive * 100}%` }} />
          </div>
          <span style={{ width: 40, textAlign: "right" }}>{formatPercent(result.probability_positive * 100, 0)}</span>
        </div>
        <div className="prob-bar-row">
          <span style={{ width: 56 }}>Negative</span>
          <div className="prob-bar-track">
            <div className="prob-bar-fill negative" style={{ width: `${result.probability_negative * 100}%` }} />
          </div>
          <span style={{ width: 40, textAlign: "right" }}>{formatPercent(result.probability_negative * 100, 0)}</span>
        </div>
      </div>

      <div className="sentiment-result-meta">
        Model: {result.model_name} {result.translated && "· translated before analysis"}
      </div>
    </div>
  );
}
