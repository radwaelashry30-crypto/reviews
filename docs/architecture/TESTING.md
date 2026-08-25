# Testing

## Backend

```bash
cd backend
pytest -q
```

67 tests across 10 files, all passing when model artifacts are present. Artifact-dependent tests (BERT/CNN2D/ABSA-specific) skip cleanly with a clear reason when `ALLOW_EXTERNAL_MODEL_DOWNLOADS=false` (the default) rather than fake a pass — see individual test files for the skip pattern.

| File | Covers |
|---|---|
| `test_health_api.py` | `/health` endpoint |
| `test_models.py` | Model artifact loading (`strict=True` state-dict checks) |
| `test_model_registry.py` | Lazy-loading, env-var gating (`ENABLE_BERT`, `ALLOW_EXTERNAL_MODEL_DOWNLOADS`) |
| `test_preprocessing.py` | Text cleaning, tokenization, dedup-before-split |
| `test_data_grain.py` | Grain-correctness of analytics KPIs (order vs. order-item level) |
| `test_analytics_api.py` | Dashboard/analytics endpoints |
| `test_sentiment_api.py` | `/predict`, `/predict-batch`, `/pipeline`, `/explain`, upload-file persistence |
| `test_batch_upload.py` | CSV/XLSX batch classification, advanced analysis (aspects/trend/top-words), oversized-file rejection |
| `test_absa.py` | Aspect keyword-presence gate (regression test for the confirmed hallucination bug) |
| `test_rate_limiting.py` | Per-IP rate limiting on `/explain` (regression test for the no-rate-limiting gap) |

## Frontend

```bash
cd frontend
npm run typecheck
npm run build
```

No dedicated frontend unit-test suite exists; correctness is currently verified via `tsc --noEmit` (type safety), a production build, and manual browser verification during development (console-error checks, real API round-trips against the local backend). This is a known gap — see `RELEASE_CHECKLIST.md`.

## Manual verification pattern used during development

For UI changes, the local dev server is started (`npm run dev` in `frontend/`, `uvicorn app.main:app` in `backend/`) and exercised via a real browser session: upload a test CSV, confirm charts render with real data, check `read_console_messages` for JS errors, confirm network requests return the expected shape. This is documented behavior, not automated — a future improvement would be Playwright/Cypress E2E coverage of the batch-upload and review-analyzer flows.

## Regenerating audit evidence

```bash
# Calibration / threshold analysis (validation split only)
python backend/scripts/calibration_analysis.py --model both

# CNN2D negation-fix retraining report
python backend/scripts/retrain_cnn2d_negation_augmented.py --apply

# BERT late-delivery-fix retraining report
python backend/scripts/retrain_bert_late_delivery_augmented.py --apply
```
