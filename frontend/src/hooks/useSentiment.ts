import { useState } from "react";
import * as sentimentApi from "../api/sentimentApi";
import { ApiClientError } from "../types/api";
import type { FullPipelineRequest, FullPipelineResponse, SentimentPrediction, SentimentPredictionRequest } from "../types/sentiment";

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

/** Task 1 -> Task 2 (if Negative) -> Task 3, all in one call. */
export function useFullPipeline() {
  const [result, setResult] = useState<FullPipelineResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiClientError | null>(null);

  async function analyze(request: FullPipelineRequest) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await sentimentApi.analyzeFullPipeline(request);
      setResult(data);
    } catch (e) {
      setError(e as ApiClientError);
    } finally {
      setLoading(false);
    }
  }

  return { result, loading, error, analyze };
}
