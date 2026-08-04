import { useState } from "react";
import * as sentimentApi from "../api/sentimentApi";
import { ApiClientError } from "../types/api";
import type { SentimentPrediction, SentimentPredictionRequest } from "../types/sentiment";

export function useSentimentPrediction() {
  const [result, setResult] = useState<SentimentPrediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiClientError | null>(null);

  async function predict(request: SentimentPredictionRequest) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await sentimentApi.predictSentiment(request);
      setResult(data);
    } catch (e) {
      setError(e as ApiClientError);
    } finally {
      setLoading(false);
    }
  }

  return { result, loading, error, predict };
}
