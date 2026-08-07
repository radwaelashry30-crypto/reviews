import { ErrorState } from "../components/ErrorState";
import { SentimentForm } from "../components/SentimentForm";
import { SentimentResult } from "../components/SentimentResult";
import { useSentimentPrediction } from "../hooks/useSentiment";

export function SentimentPage() {
  const { result, loading, error, predict } = useSentimentPrediction();

  return (
    <div className="page">
      <div className="sentiment-hero">
        <span className="eyebrow">Review Analyzer</span>
        <h1>What is this review really saying?</h1>
        <p className="page-subtitle">
          Paste any customer review and the model reads it the way a human would — is this
          customer happy or frustrated? Trained on tens of thousands of real Olist marketplace
          reviews. Results are a probabilistic, dataset-dependent estimate, not an objective
          judgment of the review.
        </p>
      </div>

      <div className="sentiment-layout">
        <div className="sentiment-form-card">
          <SentimentForm onSubmit={predict} loading={loading} />
        </div>

        <div>
          <ErrorState error={error} />
          {result ? (
            <SentimentResult result={result} />
          ) : (
            !error && (
              <div className="sentiment-empty">
                <svg width="30" height="30" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M6 9.5C6 8.12 7.12 7 8.5 7h15C24.88 7 26 8.12 26 9.5v8c0 1.38-1.12 2.5-2.5 2.5h-11l-4.5 4v-4l-1-.03A2.5 2.5 0 0 1 5 17V9.5Z"
                    stroke="currentColor" strokeWidth="1.4"
                  />
                  <circle cx="12" cy="13.5" r="1" fill="currentColor" />
                  <circle cx="16" cy="13.5" r="1" fill="currentColor" />
                  <circle cx="20" cy="13.5" r="1" fill="currentColor" />
                </svg>
                <span>Your review's sentiment will appear here.</span>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
