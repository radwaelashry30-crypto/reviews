import { useEffect } from "react";
import { useFeedback } from "../hooks/useSentiment";
import type { SentimentPrediction } from "../types/sentiment";
import { formatPercent } from "../utils/formatters";

export function SentimentResult({ result, analysisId }: { result: SentimentPrediction; analysisId?: string | null }) {
  const isPositive = result.label === "Positive";
  const feedback = useFeedback();

  // New analysis -> forget any feedback state from the previous one.
  useEffect(() => {
    feedback.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId]);

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

      {analysisId && (
        <div className="sentiment-feedback">
          {feedback.submitted ? (
            <span className="limitations-note">Thanks for the feedback.</span>
          ) : (
            <>
              <span className="sentiment-feedback-prompt">Was this right?</span>
              <button
                type="button"
                className="feedback-btn"
                disabled={feedback.loading}
                onClick={() => feedback.submit(analysisId, true)}
                aria-label="Prediction was correct"
              >
                Correct
              </button>
              <button
                type="button"
                className="feedback-btn"
                disabled={feedback.loading}
                onClick={() => feedback.submit(analysisId, false)}
                aria-label="Prediction was wrong"
              >
                Wrong
              </button>
            </>
          )}
          {feedback.error && <span className="state state-error">Couldn't save feedback.</span>}
        </div>
      )}
    </div>
  );
}
