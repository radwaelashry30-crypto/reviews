# Changelog

Curated summary of major changes. Full commit history: `git log`.

## 2026-08-16 — Security and reliability audit round

- **Fixed**: unbounded batch-upload file reads (memory-exhaustion risk on the 512MB deployment) — now capped at 5MB via bounded chunked reading before parsing.
- **Added**: per-IP rate limiting (slowapi) across all sentiment endpoints — previously none existed.
- **Fixed**: confirmed ABSA hallucination — the aspect model was forced to score all 5 fixed aspects on every review regardless of content ("product quality: Positive 75%" on a delivery-only review). Now gated behind a keyword-presence check; unmentioned aspects report "Not mentioned" instead of a guess.
- **Fixed**: fake-review detector's disclaimer strengthened with the concrete paraphrase-instability finding (99.9%→0.1% confidence from a pure synonym swap); frontend no longer presents the verdict with confident red/green styling.
- **Added**: threshold and calibration analysis (Brier score, ECE, threshold sweep) for BERT and CNN2D on the validation split — confirmed 0.5 is already near-optimal for both, documented in `MODEL_COMPARISON_AUDIT.md` §8.
- **Removed**: dead `DEBUG` config setting (defined, never referenced anywhere in the app).
- Added `MODEL_CARD.md`, `TESTING.md`, `RELEASE_CHECKLIST.md`, this changelog.

## 2026-08 — Advanced batch analysis + branding

- Added opt-in "advanced" batch-upload mode: aspect breakdown, fake-review screening, sentiment trend (weekly, when a date column is present), and most-influential-words — all sampled/bounded, never run on a full large upload unconditionally.
- Wired in the real "Baseera" logo and a gold/amber brand palette across the site (header, favicon, Overview-page hero, all charts recolored from library defaults).
- Expanded the main dashboard from 4 to 7 charts (payment methods, top customer cities, top product categories by revenue) using data already exposed by existing endpoints.

## 2026-08 — Model fixes

- **Fixed** a confirmed BERT blind spot: blunt late-delivery complaints ("the shipment coming late") were classified Positive at 99.5% confidence. Continued fine-tuning on real + synthetic negative delay examples dropped the false-positive rate on real delay complaints from 11.1% to 1.0% with no regression elsewhere.
- Investigated a much larger negation-augmentation dataset for CNN2D (300K+ rows) — found it performed *worse* than the smaller, already-deployed fix; documented and did not apply, rather than ship a regression for the sake of "more data."

## 2026-08 — Persistence and UX

- Batch-upload results now persist server-side for 7 days (JSON-file store with TTL) so navigating away and back doesn't require re-uploading; added a downloadable self-contained HTML dashboard export.
- Renamed the project from its working codename to "Baseera" throughout backend, frontend, and docs.

## 2026-08 — Core pipeline

- Added Task 2 (fake-review check) + Task 3 (aspect-based sentiment) to the live inference pipeline; fixed a real CNN2D negation bug found during that work.
- Added CSV/Excel batch review upload — the project's core requested feature.
- Wired SHAP explainability into the API and frontend.
- Fixed an OOM crash on 512MB-RAM deployments (the analytics repository was loading full unused datasets); fixed a false `NETWORK_ERROR` caused by a client timeout shorter than Render's cold-start wake time; fixed a 404 on direct navigation to client-side routes on Vercel.

## Earlier — Foundation

- Converted the original single-notebook research project into a modular FastAPI backend + React/TypeScript frontend, with genuine trained BERT and CNN2D checkpoints (verified via `strict=True` state-dict loading, not placeholders).
- Full data-quality, data-grain, and data-leakage audits with corrected numbers (`DATA_QUALITY_AUDIT.md`, `DATA_GRAIN_AUDIT.md`, `DATA_LEAKAGE_AUDIT.md`) — the original notebook's split leaked 1,097 duplicate review texts across train/val/test; corrected via dedupe-before-split.
- Deployed live: backend on Render, frontend on Vercel.
