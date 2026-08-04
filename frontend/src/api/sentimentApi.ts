import { apiPost } from "./client";
import type {
  BatchPredictionRequest, BatchPredictionResponse, SentimentPrediction, SentimentPredictionRequest,
} from "../types/sentiment";

export function predictSentiment(request: SentimentPredictionRequest): Promise<SentimentPrediction> {
  return apiPost<SentimentPrediction>("/sentiment/predict", request);
}

export function predictSentimentBatch(request: BatchPredictionRequest): Promise<BatchPredictionResponse> {
  return apiPost<BatchPredictionResponse>("/sentiment/predict-batch", request);
}
