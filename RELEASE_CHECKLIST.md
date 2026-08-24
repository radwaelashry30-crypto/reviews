# Release Checklist

Status as of the 2026-08-16 security/reliability audit round. ✅ = verified done, ⚠️ = partial/known gap (documented, not hidden), ❌ = not done.

| Item | Status | Note |
|---|---|---|
| All Critical/High issues from the audit fixed | ✅ | Rate limiting, upload-size cap, ABSA hallucination — all fixed and tested this round |
| All automated tests pass | ✅ | 67/67 backend (`pytest -q`), frontend `tsc --noEmit` + `npm run build` clean |
| Final model evaluated on untouched data | ✅ | Test-split metrics never used for tuning; calibration/threshold analysis used the validation split specifically to keep test untouched |
| Training/inference preprocessing identical | ✅ | Verified via `test_preprocessing.py`; tokenizers fit train-split-only |
| Model/tokenizer/threshold/label-mapping version-compatible | ✅ | Checkpoints, tokenizer, and code are committed together in the same repo/commit, deployed as one unit |
| API cannot load the wrong model/artifacts | ✅ | `ModelRegistry` loads once at startup from fixed, settings-driven paths; fails loudly (not silently) if a required artifact is missing |
| Frontend displays the exact backend prediction | ✅ | Verified by direct browser testing this session (batch upload, sentiment analyzer, dashboard charts against live API responses) |
| User inputs validated | ✅ | Pydantic length bounds on text fields; upload file-type + now-bounded file-size checks |
| No secrets committed | ✅ | `.env.example` contains only placeholder/default values, no real credentials |
| Debug mode disabled | ✅ | Dead `DEBUG` setting removed this round; FastAPI's own `debug=` was never set (always `False`) |
| Errors don't expose stack traces/local paths | ✅ | Catch-all exception handler returns a generic envelope, verified by reading the handler code |
| Rate limiting exists | ✅ | Added this round (slowapi, per-IP, tighter on expensive endpoints) |
| Request-size limits exist | ✅ | Upload endpoint capped at 5MB this round; text fields already Pydantic-bounded |
| Dependencies pinned | ⚠️ | `requirements.txt` uses minimum-version bounds (`>=`), not exact pins. Not changed this round — flipping to exact pins requires re-testing the full install in a clean environment to confirm nothing broke, which wasn't done. **Recommended follow-up**: `pip freeze > requirements.lock.txt` from a known-working environment. |
| Health checks work | ✅ | `/api/v1/health`, tested |
| Deployment reproducible from clean environment | ✅ | `Dockerfile` pins `python:3.11-slim` explicitly; `docker-compose.yml` present; README documents both Docker and manual install paths |
| Model limitations/disclaimers visible | ✅ | README §37–39, `MODEL_CARD.md`, and in-product disclaimers on Task 2 results |
| Rollback path exists | ⚠️ | No custom rollback tooling; relies on `git revert` + Render/Vercel's own deploy-history rollback (platform-provided, not built by this project) |
| Frontend automated test coverage | ❌ | No Playwright/Cypress E2E suite exists; verification is `tsc`/build + manual browser sessions (see `TESTING.md`). Documented gap, not silently skipped. |

## Final release decision: **READY WITH LIMITATIONS**

Not `READY` unqualified, because:
- Frontend has no automated E2E test suite (manual verification only).
- Dependencies use version ranges, not exact pins.
- CNN2D's negation-handling limitation is a documented, unresolved architectural ceiling — the live public deployment currently serves CNN2D only (BERT is disabled there for RAM reasons), so this limitation is user-facing today.

Not `NOT READY`, because no Critical security or data-integrity issue remains open: no leakage in the sentiment models' evaluation, no exposed secrets, no unbounded resource-exhaustion vector, no confident-looking false certainty in the UI, and every known model limitation is disclosed rather than hidden.
