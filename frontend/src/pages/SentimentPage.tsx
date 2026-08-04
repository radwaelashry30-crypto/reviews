import { ErrorState } from "../components/ErrorState";
import { SentimentForm } from "../components/SentimentForm";
import { SentimentResult } from "../components/SentimentResult";
import { useSentimentPrediction } from "../hooks/useSentiment";

export function SentimentPage() {
  const { result, loading, error, predict } = useSentimentPrediction();

  return (
    <div className="page">
      <h1>Review Sentiment Analysis</h1>
      <p className="page-subtitle">
        Predicts whether a customer review reads as Positive or Negative. This is a probabilistic,
        dataset-dependent estimate -- not an objective judgment of the review.
      </p>
      <SentimentForm onSubmit={predict} loading={loading} />
      <ErrorState error={error} />
      {result && <SentimentResult result={result} />}
    </div>
  );
}
