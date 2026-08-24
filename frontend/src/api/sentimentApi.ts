import { apiGet, apiPost, apiPostFile } from "./client";
import type {
  BatchPredictionRequest, BatchPredictionResponse, ExplainResponse, FeedbackRequest, FileUploadResponse,
  FullPipelineRequest, FullPipelineResponse, ModelName, SentimentPrediction, SentimentPredictionRequest,
} from "../types/sentiment";

export function predictSentiment(request: SentimentPredictionRequest): Promise<SentimentPrediction> {
  return apiPost<SentimentPrediction>("/sentiment/predict", request);
}

export function predictSentimentBatch(request: BatchPredictionRequest): Promise<BatchPredictionResponse> {
  return apiPost<BatchPredictionResponse>("/sentiment/predict-batch", request);
}

export function analyzeFullPipeline(request: FullPipelineRequest): Promise<FullPipelineResponse> {
  return apiPost<FullPipelineResponse>("/sentiment/pipeline", request);
}

export function explainSentiment(text: string): Promise<ExplainResponse> {
  return apiPost<ExplainResponse>("/sentiment/explain", { text });
}

// Advanced mode runs the full pipeline (aspect analysis) over a sample of
// rows, which is meaningfully slower than the base pass -- give it more
// room than the default upload timeout.
const ADVANCED_UPLOAD_TIMEOUT_MS = 300_000;

export function uploadReviewFile(file: File, modelName: ModelName, advanced = false): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("model_name", modelName);
  formData.append("advanced", String(advanced));
  return apiPostFile<FileUploadResponse>("/sentiment/upload-file", formData, advanced ? ADVANCED_UPLOAD_TIMEOUT_MS : undefined);
}

/** Retrieves a previously classified upload (kept 7 days) without re-uploading. */
export function getUploadedResult(uploadId: string): Promise<FileUploadResponse> {
  return apiGet<FileUploadResponse>(`/sentiment/upload-file/${uploadId}`);
}

/** Thumbs-up/down on a saved analysis. Only works when the backend has a
 * database configured (see DATABASE_SETUP.md) -- callers should only offer
 * this when `analysis_id` is non-null on the original prediction. */
export function submitFeedback(analysisId: string, feedback: FeedbackRequest): Promise<{ feedback_id: string; analysis_id: string; is_correct: boolean }> {
  return apiPost(`/sentiment/analyses/${analysisId}/feedback`, feedback);
}
