import type { SentimentPrediction } from "../types/sentiment";
import { formatPercent } from "../utils/formatters";

export function SentimentResult({ result }: { result: SentimentPrediction }) {
  const isPositive = result.label === "Positive";
  return (
    <div className={`sentiment-result ${isPositive ? "positive" : "negative"}`}>
      <div className="sentiment-result-label">{result.label}</div>
      <div className="sentiment-result-confidence">Confidence: {formatPercent(result.confidence * 100)}</div>
      <div className="sentiment-result-probs">
        <span>Positive: {formatPercent(result.probability_positive * 100)}</span>
        <span>Negative: {formatPercent(result.probability_negative * 100)}</span>
      </div>
      <div className="sentiment-result-meta">
        Model: {result.model_name} {result.translated && "(translated before analysis)"}
      </div>
    </div>
  );
}
