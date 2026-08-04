// Mirrors backend/app/schemas/sentiment.py

export type ModelName = "bert" | "cnn2d";
export type SentimentLabel = "Negative" | "Positive";

export interface SentimentPredictionRequest {
  text: string;
  model_name: ModelName;
  source_language: "en" | "pt";
  translate: boolean;
}

export interface SentimentPrediction {
  label: SentimentLabel;
  class_id: number;
  probability_positive: number;
  probability_negative: number;
  confidence: number;
  model_name: string;
  source_language: string;
  translated: boolean;
  cleaned_text: string;
}

export interface BatchPredictionItem {
  id: string;
  text: string;
}

export interface BatchPredictionRequest {
  items: BatchPredictionItem[];
  model_name: ModelName;
}

export interface BatchPredictionResultItem extends SentimentPrediction {
  id: string;
}

export interface BatchPredictionResponse {
  results: BatchPredictionResultItem[];
  n_items: number;
}
