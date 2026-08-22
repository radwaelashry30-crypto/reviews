# Changelog

Curated summary of major changes. Full commit history: `git log`.

## 2026-08-22 — ABSA rebuilt on CNN2D; fake-review live on production; repo renamed

- **Replaced the ~738MB external ABSA model** (`yangheng/deberta-v3-base-absa-v1.1`, previously off by default on the free-tier deployment for the same memory reasons as BERT) with CNN2D scoring the RAKE-located clause discussing each aspect -- zero additional model weights, zero new dependencies, live on production at zero extra RAM cost. Two smaller external replacements were evaluated and rejected first: a SetFit-based model whose `sentence-transformers` -> `setfit` dependency chain installed a full TensorFlow (500MB+) as a transitive requirement (confirmed by actually installing it -- a net size increase despite smaller model weights), and several small DistilBERT-based ABSA models on the Hub with single-digit download counts and no independent verification. Also fixed a real accuracy bug found while testing the new approach: clause splitting only on sentence punctuation missed comma-separated clauses ("Great value for the price, but the packaging was crushed" scored both aspects identically); now also splits on commas/semicolons and contrastive conjunctions.
- **Enabled the fake-review ensemble on live production** in `FAKE_REVIEW_TFIDF_ONLY` mode (the ~350KB TF-IDF component alone, independently measured at 0/188 confident flips) -- verified directly against the live API with real negative-review text before and after, `/health` confirmed stable.
- **Published the fake-review ensemble on Hugging Face** (`RadwaElashry2030/baseera-fake-review-ensemble`) with a full model card documenting the investigation, cross-linked from `README.md` and `MODEL_COMPARISON_AUDIT.md`.
- Renamed the GitHub repository to `baseera-marketplace-analytics`; updated all internal references (README, DEPLOYMENT.md, the HF model card's GitHub links) and confirmed the live Render deployment and CI were unaffected by the rename.
- Added `PROJECT_JOURNEY.md` (+ PDF): a single chronological record of every phase, every problem found, and the actual fix applied and verified for each, across the full project history.

## 2026-08-19 — Fake-review detector replaced; production OOM/CORS fixes

- **Replaced the fake-review detector** with a DistilBERT (paraphrase-consistency fine-tuned) + TF-IDF/Logistic-Regression ensemble, trained on the Ott et al. Deceptive Opinion Spam Corpus (genuinely human-verified deceptive-vs-truthful labels, not a proxy). Two prior checkpoints (an external model and a from-scratch retrain on a different dataset) had both failed a paraphrase-stability test the same way; the new ensemble passed it with statistical backing over the full held-out test split (0/300 confident flips, 95% CI upper bound 1.3%) rather than a handful of examples. A candidate dataset (Amazon "spam/non-spam", Kaggle) was inspected and rejected before training — its label turned out to be a 1:1 proxy for star rating, not a genuine judgment. Full investigation: `MODEL_COMPARISON_AUDIT.md` §9.
- **Fixed a real production outage cause**: `_check_metrics_freshness()` (added in the security/reliability round below) read the full ~670MB BERT checkpoint into memory via `Path.read_bytes()` on every startup, regardless of `ENABLE_BERT`. On Render's 512MB free instance this alone exceeded the memory limit and silently killed every deploy since the check was added — the live site had been running a stale build for some time without anyone noticing, since `/health` still reported "healthy" from the old process. Fixed by hashing in 1MB chunks and skipping the check entirely when `ENABLE_BERT=false`.
- **Fixed a real CORS gap**: `FRONTEND_ORIGINS` on the live Render service didn't match the actual deployed Vercel URL, so the public dashboard silently failed every API call with `NETWORK_ERROR` despite the backend itself being fully healthy.
- Hardened `backend/Dockerfile` into a genuine multi-stage build (builder stage for pip/wheel-building, final stage copies only installed packages + source) and switched to the CPU-only PyTorch wheel (this app never touches a GPU in production) instead of the default CUDA-bundled one — verified via a GitHub Actions CI `docker` job (build + boot + real `/api/v1/health` check) before merging, not shipped straight to the live deployment unverified.
- Added a GitHub Actions CI workflow (backend tests, frontend typecheck/test/build, Docker build+boot) after a 22-issue technical review; fixed the two real failures the first CI run caught (a Vite/Vitest version mismatch, and a `fastapi==0.119.1`+`pydantic==2.13.4` combination with a confirmed `UploadFile` bug).

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

- **Attempted a fix** for a confirmed BERT blind spot: blunt late-delivery complaints ("the shipment coming late") were classified Positive at 99.5% confidence. Continued fine-tuning on real + synthetic negative delay examples. **Correction (2026-08-18):** the originally reported "11.1% → 1.0%" false-positive-rate improvement was measured on the full train+val+test dataset — including the exact training rows the model had just been fit on — not a held-out set; a follow-up technical review caught this. Re-measured correctly on the test split only (94 genuinely-negative late/delay rows, small sample): 3.2% → 5.3%, not a statistically distinguishable change (95% CIs overlap heavily). Overall test-set f1_macro did improve slightly (0.9303 → 0.9325, no regression), so the checkpoint is not harmful, but the specific late-delivery blind spot is not demonstrably fixed by this augmentation — see `results/bert_late_delivery_augmentation_report.json` and `scripts/retrain_bert_late_delivery_augmented.py`.
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
