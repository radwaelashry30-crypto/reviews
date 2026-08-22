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
  /** Present when the backend has a database configured (see DATABASE_SETUP.md); null otherwise. */
  analysis_id: string | null;
  /** True only when this response was replayed from a matching Idempotency-Key, not freshly computed. */
  idempotent_replay?: boolean;
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
  absa_model: "cnn2d" | "deberta";
}

export interface FakeCheckResult {
  available: boolean;
  reason?: string;
  model?: string;
  is_fake?: boolean;
  fake_probability?: number;
  /** "FAKE" / "REAL" / "UNCERTAIN" -- UNCERTAIN when fake_probability lands within the model's own margin of its 0.5 decision boundary, rather than forcing a confident guess. */
  verdict?: "FAKE" | "REAL" | "UNCERTAIN";
  label_semantics_verified?: boolean;
  disclaimer?: string;
  /** False only when verdict is UNCERTAIN. */
  reliable?: boolean;
}

export interface AspectResult {
  aspect: string;
  sentiment: "Positive" | "Negative" | "Neutral" | "Not mentioned" | "UNKNOWN";
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
  /** Present when the backend has a database configured (see DATABASE_SETUP.md); null otherwise. */
  analysis_id: string | null;
}

export interface FeedbackRequest {
  is_correct: boolean;
  comment?: string;
}

// -- SHAP explanation (BERT only) --

export interface TokenContribution {
  token: string;
  shap_value: number;
}

export interface ExplainResponse {
  available: boolean;
  reason?: string;
  top_tokens_toward_positive?: TokenContribution[];
}

// -- CSV/Excel batch file upload --

export interface FileRowResult {
  row: number;
  text: string;
  label: "Positive" | "Negative" | "ERROR";
  confidence?: number;
  probability_positive?: number;
  probability_negative?: number;
  error?: string;
}

export interface TopWords {
  top_positive_words: { word: string; count: number }[];
  top_negative_words: { word: string; count: number }[];
}

export interface TimeTrendPoint {
  period: string;
  n: number;
  positive_pct: number;
}

export type TimeTrend =
  | { available: true; granularity: "week"; date_column_used: string; points: TimeTrendPoint[] }
  | { available: false; reason: string };

export type FakeReviewSummary =
  | {
      available: true;
      n_screened_negative: number;
      n_flagged_fake: number;
      flagged_pct: number;
      methodology_note: string;
    }
  | { available: false; reason: string };

export interface AspectSummaryRow {
  aspect: string;
  n: number;
  n_mentioned: number;
  mentioned_pct: number;
  /** Positive/neutral/negative % are computed among n_mentioned rows only (see mentioned_pct for coverage). */
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
}

export type AspectSummary =
  | { available: true; sample_size: number; per_aspect: AspectSummaryRow[]; methodology_note: string }
  | { available: false; reason: string };

export interface FileUploadResponse {
  filename: string;
  text_column_used: string;
  model_name: string;
  total_rows_in_file: number;
  rows_processed: number;
  truncated: boolean;
  max_rows_supported: number;
  n_classified: number;
  n_positive: number;
  n_negative: number;
  n_skipped_empty_or_error: number;
  positive_pct: number;
  negative_pct: number;
  upload_id?: string;
  retention_days?: number;
  created_at?: string;
  expires_at?: string;
  results: FileRowResult[];
  top_words?: TopWords;
  time_trend?: TimeTrend;
  advanced_sample_size?: number;
  fake_review_summary?: FakeReviewSummary;
  aspect_summary?: AspectSummary;
}
