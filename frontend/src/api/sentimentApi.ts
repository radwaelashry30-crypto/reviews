import { apiPost, apiPostFile } from "./client";
import type {
  BatchPredictionRequest, BatchPredictionResponse, ExplainResponse, FileUploadResponse, FullPipelineRequest,
  FullPipelineResponse, ModelName, SentimentPrediction, SentimentPredictionRequest,
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

export function uploadReviewFile(file: File, modelName: ModelName): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("model_name", modelName);
  return apiPostFile<FileUploadResponse>("/sentiment/upload-file", formData);
}
