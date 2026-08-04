// Mirrors backend/app/schemas/common.py + errors.py -- keep field names identical.

export interface ApiMeta {
  api_version: string;
  model_version: string | null;
  request_id: string;
}

export interface ApiResponse<T> {
  success: true;
  data: T;
  meta: ApiMeta;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ApiErrorResponse {
  success: false;
  error: ApiErrorDetail;
  meta: Record<string, unknown>;
}

export class ApiClientError extends Error {
  code: string;
  details: Record<string, unknown>;
  status: number;

  constructor(status: number, error: ApiErrorDetail) {
    super(error.message);
    this.name = "ApiClientError";
    this.code = error.code;
    this.details = error.details;
    this.status = status;
  }
}
