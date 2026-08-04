import { useState } from "react";
import * as segmentationApi from "../api/segmentationApi";
import { ApiClientError } from "../types/api";
import type { RfmPredictionRequest, RfmPredictionResponse } from "../types/segmentation";
import { useAsync } from "./useAsync";

export const useRfmSummary = () => useAsync(segmentationApi.getRfmSummary, []);

export function useRfmPrediction() {
  const [result, setResult] = useState<RfmPredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiClientError | null>(null);

  async function predict(request: RfmPredictionRequest) {
    setLoading(true);
    setError(null);
    try {
      const data = await segmentationApi.predictRfmSegment(request);
      setResult(data);
    } catch (e) {
      setError(e as ApiClientError);
    } finally {
      setLoading(false);
    }
  }

  return { result, loading, error, predict };
}
