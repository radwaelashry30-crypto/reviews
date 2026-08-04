import axios, { type AxiosInstance, AxiosError } from "axios";
import { ApiClientError, type ApiErrorResponse, type ApiResponse } from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const httpClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// Placeholder for future authentication: set a token here and it's applied to every request.
export function setAuthToken(token: string | null): void {
  if (token) {
    httpClient.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete httpClient.defaults.headers.common.Authorization;
  }
}

function toApiClientError(error: unknown): ApiClientError {
  if (error instanceof AxiosError && error.response) {
    const body = error.response.data as ApiErrorResponse | undefined;
    if (body?.error) {
      return new ApiClientError(error.response.status, body.error);
    }
    return new ApiClientError(error.response.status, {
      code: "UNKNOWN_ERROR",
      message: error.message,
      details: {},
    });
  }
  return new ApiClientError(0, { code: "NETWORK_ERROR", message: "Could not reach the API server.", details: {} });
}

export async function apiGet<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  try {
    const resp = await httpClient.get<ApiResponse<T>>(path, { params });
    return resp.data.data;
  } catch (error) {
    if (import.meta.env.DEV) console.error(`GET ${path} failed`, error);
    throw toApiClientError(error);
  }
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  try {
    const resp = await httpClient.post<ApiResponse<T>>(path, body);
    return resp.data.data;
  } catch (error) {
    if (import.meta.env.DEV) console.error(`POST ${path} failed`, error);
    throw toApiClientError(error);
  }
}
