# Frontend Integration Guide

## 1. Start the backend

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```
Opens at `http://localhost:5173`.

## 3. Configure `VITE_API_BASE_URL`

Copy `frontend/.env.example` to `frontend/.env` and adjust if the backend runs elsewhere:
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```
Read once in `frontend/src/api/client.ts` via `import.meta.env.VITE_API_BASE_URL` — never hard-coded in a component.

## 4. Type <-> schema mapping

| Backend Pydantic schema | Frontend TS type | File |
|---|---|---|
| `schemas.sentiment.SentimentPredictionRequest` | `SentimentPredictionRequest` | `frontend/src/types/sentiment.ts` |
| `schemas.sentiment.SentimentPrediction` | `SentimentPrediction` | same |
| `schemas.analytics.BusinessSummary` | `BusinessSummary` | `frontend/src/types/analytics.ts` |
| `schemas.segmentation.RfmPredictionRequest/Response` | `RfmPredictionRequest`/`RfmPredictionResponse` | `frontend/src/types/segmentation.ts` |

Field names are identical on both sides by convention (`shared/api_contract.json` documents the simplified contract). If you change a Pydantic field, update the matching TS interface in the same commit.

## 5. Calling sentiment prediction

```ts
import { predictSentiment } from "../api/sentimentApi";
const prediction = await predictSentiment({ text, model_name: "bert", source_language: "en", translate: false });
```
`predictSentiment` throws an `ApiClientError` (see `types/api.ts`) on failure — catch it in the calling hook (see `hooks/useSentiment.ts`), never in the component itself.

## 6. Calling dashboard endpoints

```ts
import { getBusinessSummary } from "../api/analyticsApi";
const summary = await getBusinessSummary();
```
Prefer the `use*` hooks in `frontend/src/hooks/` (`useBusinessSummary`, `useMonthlyOrders`, ...) inside pages — they wrap loading/error state via the shared `useAsync` hook.

## 7. Loading states

Every page-level hook returns `{ data, loading, error }`. Render `<LoadingState />` while `loading`, `<ErrorState error={error} />` when set, and the real UI once `data` is populated. See `pages/DashboardPage.tsx` for the pattern.

## 8. Displaying API errors

`ErrorState` reads `ApiClientError.code` and `.message` (mapped 1:1 from the backend's `error.code` / `error.message`). Never render raw Axios error objects.

## 9. Adding a new endpoint

1. Backend: add a Pydantic schema (if needed) in `app/schemas/`, business logic in `app/services/`, and a route in `app/api/v1/endpoints/`; register it in `app/api/v1/router.py`.
2. Frontend: add the matching TS type in `src/types/`, an API function in `src/api/`, and a `use*` hook in `src/hooks/` if a page needs it.
3. Keep field names identical across both sides.

## 10. Adding authentication later

`app/core/security.py` has a `get_optional_api_key` dependency stub already wired for future use; `frontend/src/api/client.ts` has `setAuthToken()` ready to attach a bearer token to every request. Enforce it in `security.py` and call `setAuthToken()` after login — no other files need to change.

## 11. Deploying backend and frontend separately

- Backend: containerize with `backend/Dockerfile`, deploy behind any ASGI-compatible host (Uvicorn/Gunicorn). Set `FRONTEND_ORIGINS` to the deployed frontend's real origin.
- Frontend: `npm run build` produces `frontend/dist/` — a static bundle deployable to any static host (Netlify, S3+CloudFront, Nginx). Set `VITE_API_BASE_URL` to the deployed backend's public URL at build time.

## 12. Replacing the React starter

All ML/business logic lives in the backend. The frontend only calls `src/api/*` functions and renders their results — you can rewrite every page/component without touching a single Python file, as long as you keep calling the same `/api/v1/*` endpoints.
