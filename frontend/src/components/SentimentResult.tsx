import { useEffect } from "react";
import { useFeedback } from "../hooks/useSentiment";
import { Button } from "./ui/Button";
import { StatusPill } from "./ui/Badge";
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
    <div className="bsr-sentiment-verdict">
      <div className="bsr-sentiment-verdict__head">
        <span className="bsr-sentiment-verdict__label">
          <StatusPill tone={isPositive ? "positive" : "negative"}>
            {isPositive ? "▲ Positive" : "▼ Negative"}
          </StatusPill>
        </span>
        <span className="bsr-sm bsr-sentiment-verdict__confidence">
          <strong>{formatPercent(result.confidence * 100)}</strong> model confidence
        </span>
      </div>

      <div className="bsr-sentiment-probs" role="group" aria-label="Class probability distribution">
        <div className="bsr-sentiment-prob-row">
          <span className="bsr-sentiment-prob-row__label">Positive</span>
          <div className="bsr-sentiment-prob-track">
            <div className="bsr-sentiment-prob-fill bsr-sentiment-prob-fill--positive" style={{ width: `${result.probability_positive * 100}%` }} />
          </div>
          <span className="bsr-sentiment-prob-row__value">{formatPercent(result.probability_positive * 100, 0)}</span>
        </div>
        <div className="bsr-sentiment-prob-row">
          <span className="bsr-sentiment-prob-row__label">Negative</span>
          <div className="bsr-sentiment-prob-track">
            <div className="bsr-sentiment-prob-fill bsr-sentiment-prob-fill--negative" style={{ width: `${result.probability_negative * 100}%` }} />
          </div>
          <span className="bsr-sentiment-prob-row__value">{formatPercent(result.probability_negative * 100, 0)}</span>
        </div>
      </div>

      <p className="bsr-caption bsr-sentiment-meta">
        Model: {result.model_name}
        {result.translated && " · translated before analysis"}
      </p>

      {analysisId && (
        <div className="bsr-sentiment-feedback">
          {feedback.submitted ? (
            <span className="bsr-sm">Thanks for the feedback.</span>
          ) : (
            <>
              <span className="bsr-sm bsr-sentiment-feedback__prompt">Was this right?</span>
              <Button
                type="button"
                variant="ghost"
                disabled={feedback.loading}
                onClick={() => feedback.submit(analysisId, true)}
                aria-label="Prediction was correct"
              >
                Correct
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={feedback.loading}
                onClick={() => feedback.submit(analysisId, false)}
                aria-label="Prediction was wrong"
              >
                Wrong
              </Button>
            </>
          )}
          {feedback.error && <span className="bsr-sm" style={{ color: "var(--bsr-negative)" }}>Couldn't save feedback.</span>}
        </div>
      )}
    </div>
  );
}
