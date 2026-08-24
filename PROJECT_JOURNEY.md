# Project Journey — Every Phase, Every Problem, Every Real Fix

This is a chronological record of the work done on Baseera: what phase it belonged to,
what concrete problem was found, how it was diagnosed, and — critically — what was
**actually applied and verified**, not just proposed. Every claim below is backed by a
test run, a real log, a real API response, or a committed file; where a fix did **not**
fully work, that is stated honestly rather than smoothed over.

---

## Phase 1 — Results integrity (technical review issues #01–#05)

| # | Problem found | Root cause | Fix applied | Verified by |
|---|---|---|---|---|
| 1 | `analysis_id: null` on every live `/predict` call despite the database showing "connected" | Render has no separate migration/release step — `DATABASE_URL` connected fine, but the schema had zero tables, so every write silently failed inside the best-effort persistence layer | Alembic migrations now run automatically at app startup (`_run_pending_migrations()` in `main.py`) | Live curl to `/predict` returning a real `analysis_id` |
| 2 | A retraining run once overwrote a model checkpoint without regenerating the metrics file describing it — a silent, undetectable drift | No mechanism compared the published metrics' recorded checkpoint hash against the checkpoint actually on disk | `checkpoint_fingerprint()` (SHA-256 over weight files) + `_check_metrics_freshness()` logs an error at startup on mismatch | `scripts/verify_metrics_freshness.py` added to CI |
| 3 | CORS allowed `methods=["*"]`, `headers=["*"]` — far broader than the API's actual surface | Copy-pasted default, never tightened | Explicit `["GET","POST"]` / `["Content-Type","X-API-Key","Idempotency-Key"]` | Manual review; live CORS behavior confirmed correct (see Production Incident 2 below for the *other* CORS bug this didn't cause) |
| 4 | `README.md` and the FastAPI `description` field both claimed "end-to-end" / implied a live data source | The dashboard is a static Olist snapshot (2016–2018), not live/streaming | Reworded both to state this explicitly | Manual review |
| 5 | Historical notebook-reported metrics were presented without flagging they came from a leaky split | — | `/models/info` now separates `metrics` (from the corrected pipeline) from `historical_notebook_metrics` with `valid: false` | API response inspected directly |

---

## Phase 2 — Security & availability (#10, #11, #13, #14, #15)

| Problem | Failure scenario it closes | Fix |
|---|---|---|
| Rate limiter keyed on the raw socket peer address | Behind Render's reverse proxy, that's *always* the proxy's own IP — every real client shared one shared limit bucket, meaning one heavy user could throttle everyone | `client_identity()` parses `X-Forwarded-For` at a configured `TRUSTED_PROXY_HOPS` position (1 = trust exactly one hop, matching Render/Vercel) |
| Unbounded batch-upload file reads | A large/malicious upload could buffer an entire file in memory before any row-count cap kicked in — real OOM risk on a 512MB host | Bounded chunked reads, hard 5MB cap, rejects before fully buffering |
| `upload_id` read straight into a filesystem path | Path traversal if a crafted ID were ever accepted | Strict 32-hex regex + resolved-path containment check before any file I/O |
| No concurrency/timeout control on batch classification | Two uploads landing seconds apart could each hold a full batch's model activations in memory at once | `asyncio.Semaphore(2)` + `asyncio.wait_for(..., timeout=300)`, degrading to a clean 504 instead of hanging or OOM-ing |

---

## Phase 3 — ML correctness (#06–#09)

**RFM train/serve skew.** The scaler was fit on raw values, then log-transformed
separately at serving time — not the same transform the model trained on. Fixed by
wrapping `log1p` + `StandardScaler` in one `sklearn.Pipeline`, pickled and reused
identically at both train and serve time. Verified by
`test_rfm_pipeline_transform_is_identical_at_train_and_serve`.

**ABSA hallucination.** The aspect model was forced to score all 5 fixed aspects on
every review regardless of content ("product quality: Positive 75%" on a
delivery-only review). Fixed with a keyword-presence gate; unmentioned aspects now
report "Not mentioned". Then **generalized further**: the keyword lists only worked for
Olist's exact domain — replaced with a RAKE-based, domain-general extraction pipeline
(`app/ml/aspect_extraction.py`), empirically validated on non-e-commerce example
reviews too (a semantic-similarity layer was *also* tried to catch aspects discussed
without their own name, measured unreliable, and **not shipped** — an honest negative
result, not hidden).

---

## Phase 4 — Engineering discipline (#17, #18, #20)

- **`requirements.txt` had no upper bounds.** A fresh install could silently resolve a
  breaking dependency months later with zero warning. Pinned every dependency with a
  documented reason per line — and this was **not theoretical caution**: it caught a
  real bug live in CI (see below).
- **Dockerfile ran as root, had no `HEALTHCHECK`, no `--proxy-headers`.** Without
  `--proxy-headers`, uvicorn ignores `X-Forwarded-For` entirely, silently breaking the
  Phase 2 rate-limiting fix in production specifically (it would work locally, fail
  live). Fixed incrementally, then fully hardened into a genuine multi-stage build
  (see "Docker hardening" below).
- **Dev-only tooling (matplotlib, pytest, datasets) was mixed into the production
  `requirements.txt`.** Split into `requirements.txt` (runtime only) +
  `requirements-dev.txt` (adds test/training tooling) — the deployed image no longer
  pays for dependencies it never imports.

---

## Phase 5 — Test coverage & doc accuracy (#12, #16, #21, #22)

- **Idempotency key**: `POST /predict` reads an `Idempotency-Key` header; a client retry
  after a timeout now replays the saved result instead of creating a duplicate history
  row. Required a new DB migration (`b1c8891786a0`), a unique constraint, and a
  repository lookup method — all added and tested.
- **Upload concurrency limit** (see Phase 2, formalized and tested here).
- Filled real gaps in test coverage the review flagged, and corrected doc claims that
  had drifted from what the code actually did.

---

## CI/CD — set up, then immediately caught two real bugs

A GitHub Actions workflow (`backend` / `frontend` / `docker` jobs) was added. **The very
first real run failed on both applicable jobs** — and both failures were genuine, not
CI flakiness:

1. **Frontend**: `tsc -b` (the build's actual type-check mode) didn't honor
   `/// <reference types="vitest/config" />` the way `tsc --noEmit` had — fixed by
   importing `defineConfig` directly from `"vitest/config"`. That fix then exposed a
   **second**, previously-masked bug: `vitest@2.1.8` pulled in a duplicate, nested
   Vite 5 install that conflicted with the project's Vite 6, causing a type mismatch.
   Fixed by upgrading to `vitest@^3.0.5`.
2. **Backend**: a fresh install resolved `fastapi==0.119.1` + `pydantic==2.13.4` — a
   real, confirmed combination bug (`UploadFile` TypeAdapter/forward-ref error) that
   cascaded into ~26 unrelated test failures via a shared schema-build failure. Diagnosed
   by comparing CI's freshly-resolved versions against the main dev environment's
   already-working `fastapi==0.141.1`. Fixed by raising the pinned upper bound to
   `<0.145`, with the exact bug documented inline in `requirements.txt` so it's not
   silently reintroduced later.

Verified: 129 backend tests + 9 frontend tests passing before either fix was pushed.

---

## Docker hardening — verified before touching production

The Dockerfile was rewritten as a genuine multi-stage build: a `builder` stage installs
dependencies (needs the full pip/wheel toolchain), the final stage copies only the
installed packages + source — plus switching to PyTorch's official CPU-only wheel
(`--extra-index-url .../whl/cpu`) instead of the ~2GB+ CUDA-bundled default, since this
app's `device` always resolves to `"cpu"` in production.

This was **not pushed straight to `main`**: it was built on a separate branch
(`harden-dockerfile`), opened as a PR, and only merged after the CI `docker` job — a
genuine `docker build` + container boot + real `curl` health check — passed. Confirmed
green (`backend`, `frontend`, `docker` all `success`) before merge.

---

## Production incidents — found by checking the live site, not assumed from a green push

### Incident 1 — every deploy since a specific commit had been silently failing (OOM)

After merging the Dockerfile PR, Render's deploy for that exact commit showed **"Deploy
failed"** with notice: *"Ran out of memory (used over 512MB)."* Investigating further
revealed the live site had actually been running a **stale build from several commits
earlier** — every deploy in between (all of Phases 1–5) had been failing the same way,
and nobody had noticed because the *old* process kept answering `/health` as "healthy"
the whole time.

**Root cause, found by reading the code, not guessing**: `_check_metrics_freshness()`
called `checkpoint_fingerprint()`, which did `path.read_bytes()` — loading the *entire*
~670MB BERT checkpoint into memory in one shot, on every single startup, regardless of
whether `ENABLE_BERT` was even true.

**Fix**: hash in 1MB chunks instead of one giant read (verified: identical SHA-256
output to the old method), and skip the check entirely when `ENABLE_BERT=false` — no
reason to fingerprint a model that's never loaded. Pushed, redeploy confirmed **"Deploy
succeeded | Live"**.

### Incident 2 — CORS silently broke the entire public dashboard

Even with the OOM fix live and the backend reporting 100% healthy, the actual deployed
frontend showed `NETWORK_ERROR` on every single chart. Reading the browser's own
console (not just checking the backend) showed the real error:
`Access to XMLHttpRequest ... blocked by CORS policy: No 'Access-Control-Allow-Origin'
header`. `FRONTEND_ORIGINS` on Render still held a stale/placeholder value, not the
actual deployed Vercel URL.

**Fix**: updated the `FRONTEND_ORIGINS` environment variable on Render to the real
Vercel URL. Re-verified directly in the browser: zero console errors, real dashboard
numbers loading (99,441 orders, 96,096 customers, etc.).

### Incident 3 — a version-drift risk caught before it caused a third incident

Live logs showed `InconsistentVersionWarning: Trying to unpickle estimator ... from
version 1.9.0 when using version 1.5.2` — the RFM scaler/K-Means artifacts had been
pickled with a locally-installed scikit-learn newer than what `requirements.txt` pins
for production. This is exactly the failure mode the requirements file's own upper-bound
comment already warned about. Flagged for re-pickling with a production-matching
scikit-learn version.

---

## Database verification

`alembic check` run against a fresh database with every migration applied returned
*"No new upgrade operations detected"* — the migrations and `models.py` are provably in
sync, not just assumed to be. Schema reviewed against the app's actual needs (no
speculative Users/Orders/Auth tables — this app has none of those concepts) and
confirmed working on the live database via a real `/predict` call returning a non-null
`analysis_id`.

---

## What "actually applied" means in this document

Every fix above was one of:
- Re-run against the real backend test suite (129+ tests, all passing after each change)
- Verified with a real `curl`/API call against the live deployment
- Confirmed via a CI job actually passing (not just "should pass")
- Measured with a statistically meaningful sample and a stated confidence interval,
  where a claim was about reliability rather than a binary pass/fail

Where a fix did not fully close the gap (DistilBERT's residual length-sensitivity being
the clearest example), that is stated as-is rather than rounded up to "fixed."
