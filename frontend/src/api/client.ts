import axios, { type AxiosInstance, AxiosError } from "axios";
import { ApiClientError, type ApiErrorResponse, type ApiResponse } from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// 65s: free-tier hosts (e.g. Render) spin the backend down after inactivity
// and can take "50 seconds or more" to wake on the next request (their own
// documented ceiling). A shorter timeout here fires a false NETWORK_ERROR
// while the server is still waking up, not actually unreachable.
const REQUEST_TIMEOUT_MS = 65_000;

export const httpClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
  headers: { "Content-Type": "application/json" },
});

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Retries once on timeout/network failure -- covers the case where a cold
 * backend was still waking up on the first attempt (by the second attempt,
 * ~1s later, it has very likely finished and responds quickly). Does NOT
 * retry on a real HTTP error response (4xx/5xx) -- only on no response at all. */
async function withColdStartRetry<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    const isNetworkOrTimeout = error instanceof AxiosError && !error.response;
    if (!isNetworkOrTimeout) throw error;
    await sleep(1000);
    return fn();
  }
}

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
    const resp = await withColdStartRetry(() => httpClient.get<ApiResponse<T>>(path, { params }));
    return resp.data.data;
  } catch (error) {
    if (import.meta.env.DEV) console.error(`GET ${path} failed`, error);
    throw toApiClientError(error);
  }
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  try {
    const resp = await withColdStartRetry(() => httpClient.post<ApiResponse<T>>(path, body));
    return resp.data.data;
  } catch (error) {
    if (import.meta.env.DEV) console.error(`POST ${path} failed`, error);
    throw toApiClientError(error);
  }
}

/** multipart/form-data upload -- clears the default JSON Content-Type so the
 * browser sets the correct multipart boundary itself. No cold-start retry
 * (a file upload isn't safely re-sendable mid-stream the way a small JSON
 * body is); file processing can also legitimately take longer than a normal
 * request, so this uses a longer timeout. */
export async function apiPostFile<T>(path: string, formData: FormData): Promise<T> {
  try {
    const resp = await httpClient.post<ApiResponse<T>>(path, formData, {
      headers: { "Content-Type": undefined },
      timeout: 120_000,
    });
    return resp.data.data;
  } catch (error) {
    if (import.meta.env.DEV) console.error(`POST ${path} (file) failed`, error);
    throw toApiClientError(error);
  }
}
