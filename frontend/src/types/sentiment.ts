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

// -- Full pipeline: Task 1 (sentiment) -> Task 2 (fake check, if Negative) -> Task 3 (aspects) --

export interface FullPipelineRequest {
  text: string;
  model_name: ModelName;
  source_language: "en" | "pt";
  translate: boolean;
  aspects?: string[];
}

export interface FakeCheckResult {
  available: boolean;
  reason?: string;
  model?: string;
  raw_label?: string;
  raw_confidence?: number;
  is_fake?: boolean;
  fake_probability?: number;
  label_semantics_verified?: boolean;
  disclaimer?: string;
}

export interface AspectResult {
  aspect: string;
  sentiment: "Positive" | "Negative" | "Neutral" | "UNKNOWN";
  confidence: number;
}

export interface AspectsResult {
  available: boolean;
  reason?: string;
  model?: string;
  aspects?: AspectResult[];
  methodology_note?: string;
}

export interface FullPipelineResponse {
  sentiment: SentimentPrediction;
  fake_check: FakeCheckResult | null;
  aspects: AspectsResult;
}
