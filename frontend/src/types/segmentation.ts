// Mirrors backend/app/schemas/segmentation.py

export interface RfmPredictionRequest {
  recency: number;
  frequency: number;
  monetary: number;
}

export interface RfmPredictionResponse {
  cluster_id: number;
  segment_name: string;
  input: RfmPredictionRequest;
}

export interface RfmSegmentSummaryRow {
  Segment: string;
  Recency: number;
  Frequency: number;
  Monetary: number;
  customer_count: number;
}

export interface RfmSummary {
  cluster_label_map: Record<string, string>;
  segment_summary: RfmSegmentSummaryRow[];
  n_customers: number;
}
