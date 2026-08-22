import { useEffect, useRef, useState } from "react";
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

  function reset() {
    setResult(null);
    setError(null);
  }

  return { result, loading, error, analyze, reset };
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
  // Wall-clock time for the request as measured in this browser -- NOT a
  // backend-reported field. The backend does emit a real `x-process-time-ms`
  // response header (see app/main.py's timing middleware), but it isn't in
  // CORS's Access-Control-Expose-Headers, so cross-origin JS can't read it;
  // this is measured client-side instead and must be labeled as such in the UI.
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const lastArgsRef = useRef<{ file: File; modelName: ModelName; advanced: boolean } | null>(null);

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
    lastArgsRef.current = { file, modelName, advanced };
    setLoading(true);
    setError(null);
    setResult(null);
    setDurationMs(null);
    const startedAt = performance.now();
    try {
      const data = await sentimentApi.uploadReviewFile(file, modelName, advanced);
      setResult(data);
      setDurationMs(performance.now() - startedAt);
      if (data.upload_id) localStorage.setItem(LAST_UPLOAD_ID_KEY, data.upload_id);
    } catch (e) {
      setError(e as ApiClientError);
    } finally {
      setLoading(false);
    }
  }

  /** Re-sends the exact same file/settings that produced the current error --
   * genuine retry, not a re-derived guess. */
  function retry() {
    if (lastArgsRef.current) {
      const { file, modelName, advanced } = lastArgsRef.current;
      upload(file, modelName, advanced);
    }
  }

  function reset() {
    setResult(null);
    setError(null);
    setDurationMs(null);
    lastArgsRef.current = null;
  }

  function clearSaved() {
    localStorage.removeItem(LAST_UPLOAD_ID_KEY);
    setResult(null);
  }

  return { result, loading: loading || restoring, error, upload, clearSaved, durationMs, retry, reset };
}
