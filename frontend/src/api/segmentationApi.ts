import { apiGet, apiPost } from "./client";
import type { RfmPredictionRequest, RfmPredictionResponse, RfmSummary } from "../types/segmentation";

export const getRfmSummary = (): Promise<RfmSummary> => apiGet("/segmentation/rfm-summary");
export const predictRfmSegment = (request: RfmPredictionRequest): Promise<RfmPredictionResponse> =>
  apiPost("/segmentation/predict", request);
