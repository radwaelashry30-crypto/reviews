import { useEffect, useState } from "react";
import * as sentimentApi from "../api/sentimentApi";
import { ApiClientError } from "../types/api";
import type {
  ExplainResponse, FileUploadResponse, FullPipelineRequest, FullPipelineResponse, ModelName,
  SentimentPrediction, SentimentPredictionRequest,
} from "../types/sentiment";

/** Thumbs-up/down on a saved analysis. Only usable when the prediction
 * carried a non-null analysis_id (i.e. the backend has a database
 * configured -- see DATABASE_SETUP.md). */
export function useFeedback() {
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiClientError | null>(null);

  async function submit(analysisId: string, isCorrect: boolean, comment?: string) {
    setLoading(true);
    setError(null);
    try {
      await sentimentApi.submitFeedback(analysisId, { is_correct: isCorrect, comment });
      setSubmitted(true);
    } catch (e) {
      setError(e as ApiClientError);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setSubmitted(false);
    setError(null);
  }

  return { submitted, loading, error, submit, reset };
}

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

/** SHAP token-level explanation, BERT only, on-demand (not part of the auto-run pipeline -- slower). */
export function useExplanation() {
  const [result, setResult] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiClientError | null>(null);

  async function explain(text: string) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await sentimentApi.explainSentiment(text);
      setResult(data);
    } catch (e) {
      setError(e as ApiClientError);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null);
    setError(null);
  }

  return { result, loading, error, explain, reset };
}

const LAST_UPLOAD_ID_KEY = "baseera.lastUploadId";

/** CSV/Excel batch review upload. Results are saved server-side for 7 days
 * (see backend/app/services/upload_store.py); the upload_id is remembered in
 * localStorage so reloading the page (or coming back later, within 7 days)
 * restores the same results instead of requiring a re-upload. */
export function useFileUpload() {
  const [result, setResult] = useState<FileUploadResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [error, setError] = useState<ApiClientError | null>(null);

  useEffect(() => {
    const savedId = localStorage.getItem(LAST_UPLOAD_ID_KEY);
    if (!savedId) {
      setRestoring(false);
      return;
    }
    sentimentApi
      .getUploadedResult(savedId)
      .then((data) => setResult(data))
      .catch(() => localStorage.removeItem(LAST_UPLOAD_ID_KEY)) // expired or gone -- silently drop, not an error to surface
      .finally(() => setRestoring(false));
  }, []);

  async function upload(file: File, modelName: ModelName, advanced = false) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await sentimentApi.uploadReviewFile(file, modelName, advanced);
      setResult(data);
      if (data.upload_id) localStorage.setItem(LAST_UPLOAD_ID_KEY, data.upload_id);
    } catch (e) {
      setError(e as ApiClientError);
    } finally {
      setLoading(false);
    }
  }

  function clearSaved() {
    localStorage.removeItem(LAST_UPLOAD_ID_KEY);
    setResult(null);
  }

  return { result, loading: loading || restoring, error, upload, clearSaved };
}
