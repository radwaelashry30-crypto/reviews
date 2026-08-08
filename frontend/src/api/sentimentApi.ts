import { apiPost } from "./client";
import type {
  BatchPredictionRequest, BatchPredictionResponse, FullPipelineRequest, FullPipelineResponse,
  SentimentPrediction, SentimentPredictionRequest,
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
