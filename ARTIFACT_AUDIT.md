# Artifact Audit

Source project: `C:\Users\User1\Downloads\Fake news\update-20260731T143927Z-1-001\update`
Inspected: 2026-08-04. All files below were recursively discovered and, where a genuine artifact, loaded and validated (not assumed valid by filename).

## 1. Complete file inventory (source folder)

| Path | Size | Type |
|---|---|---|
| `olist_full_eda_preprocessing_PYTORCH.ipynb` | 20.3 MB | Main notebook (151 cells), most recent (2026-08-03) |
| `olist_full_eda_preprocessing_PYTORCH.backup_pre_refactor.ipynb` | 16.9 MB | Earlier draft (121 cells), superseded |
| `New folder/olist_8_2.ipynb` | 16.9 MB | Earlier draft (149 cells), superseded |
| `models/bert_review_sentiment/config.json` | 1.2 KB | Fine-tuned BERT config |
| `models/bert_review_sentiment/model.safetensors` | 638.4 MB | Fine-tuned BERT weights |
| `models/bert_review_sentiment/tokenizer.json` | 2.5 MB | BERT tokenizer |
| `models/bert_review_sentiment/tokenizer_config.json` | 0.6 KB | BERT tokenizer config |
| `models/cnn2d_review_sentiment.pt` | 11.6 MB | CNN2D state dict |
| `models/cnn2d_tokenizer.pkl` | 105 KB | Pickled `SimpleVocabTokenizer` |
| `output/olist_cleaned_dataset.csv` | 53.0 MB | Legacy merged (order-item grain) export |
| `output/olist_cleaned_dataset.parquet` | 18.8 MB | Same, Parquet |
| `reviews_translated.csv` | 17.1 MB | 100,000 reviews, 41,723 with non-empty EN translation |
| `weights/bert_review_sentiment_epoch_0{1,2,3}.pt` | 638.5 MB each | Raw BERT `state_dict` per-epoch checkpoints (NOT full HF directories) |
| `final_pipeline_report.pdf` | 310 KB | Prior report |
| `تقرير_شامل_حالة_مشروع_...pdf` | 407 KB | Prior Arabic-language status report |

No raw Olist CSVs (`olist_orders_dataset.csv` etc.) are present anywhere in the uploaded folder. See §7.

## 2. Notebook structure summary

151 cells across 14 sections: Configuration → Imports → Utility Functions → Data Loading → Data Cleaning → Translation → EDA → Customer/Seller Behavior → Export → Sentiment Preprocessing → Dataset Splitting → Model Training (BERT §9.1, CNN2D §9.2) → Evaluation → Explainability (SHAP) → Fake Review Detection → ABSA → Insights/Recommendations → **Prediction Interface (cell 149, buggy) → Fake-News placeholder (cell 150)**.

## 3. Model artifact selection

### BERT — selected: `models/bert_review_sentiment/`
- **Reason**: this is the only genuine `save_pretrained()` output (has `config.json` + weights + tokenizer files together); the `weights/*.pt` files are raw epoch state dicts requiring the exact training-time model construction to load, and are NOT drop-in replacements for a `from_pretrained()` call.
- **Verified**: `config.json` → `architectures: ["BertForSequenceClassification"]`, `id2label: {"0":"Negative","1":"Positive"}`, `vocab_size: 105879` (bert-base-multilingual-uncased-sized, consistent with `LiYuan/amazon-review-sentiment-analysis`'s actual base architecture — **not DistilBERT**, despite the checkpoint being marketed as "for Amazon reviews"). `AutoModelForSequenceClassification.from_pretrained()` + `AutoTokenizer.from_pretrained()` both load successfully; `num_labels == 2` confirmed.

### CNN2D — selected: `models/cnn2d_review_sentiment.pt` + `artifacts/cnn2d_tokenizer.pkl`
- **Reason**: the only CNN2D checkpoint present; extracted `CNN2DReviewSentiment` class (notebook cell 131) matches it exactly.
- **Verified** (`torch.load(weights_only=True)` + `strict=True`):
  - Result: **`<All keys matched successfully>`** — no missing keys, no unexpected keys, no shape mismatches.
  - 33 state-dict keys; total trainable parameters **3,049,345** (matches the notebook's own printed count exactly).
  - `embedding.weight` shape `(30000, 100)`; `output_layer.weight` shape `(1, 32)`.
- **Tokenizer**: `SimpleVocabTokenizer`, vocab size **8,202** (matches notebook's printed "Vocabulary size (capped at 30000): 8,202" exactly), padding index 0 (implicit, never assigned to a real word), OOV index 1 (`word_index["<OOV>"] == 1`).
- **Known quirk, handled**: this pickle was serialized from the notebook's own `__main__` namespace. Unpickling it in any other process (this backend, a test, a script) requires registering `SimpleVocabTokenizer` under `__main__` first — implemented once in `ModelRegistry._load_cnn()` and in every script that loads it directly (`evaluate.py`, `inference.py`, `export_artifacts.py`).

## 4. Translation model — resolved ambiguity

Configuration cell 3 sets `TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-pt-en"`. Cell 49, run immediately before the translation cell, REASSIGNS it: `TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-ROMANCE-en"`. Cell 50's captured stdout confirms: `"Loading translation model on cpu: Helsinki-NLP/opus-mt-ROMANCE-en"`. **The model that actually produced `reviews_translated.csv` is `opus-mt-ROMANCE-en`**, not the one in the Configuration cell. This project's `translation.py` defaults to the verified-actual model and records both in `artifacts/translation_manifest.json`.

## 5. Fake-news placeholder — NOT used

Cell 150 contains `MODEL_NAME = "PUT_YOUR_MODEL_HASH_HERE"` and an unrelated fake-news classification UI. This is not a trained project artifact (the placeholder was never filled in, and even if it were, it addresses a different task — news veracity, not review sentiment). It is preserved, unmodified, in `original_project_backup/` for historical reference and is **not present anywhere in the production backend/frontend code path**.

## 6. Notebook inference bugs (cell 149) — fixed in this project

| Bug | Notebook behavior | Fix |
|---|---|---|
| Wrong model path | Tries to load `output/bert_sentiment_model.pt`, which was never saved (training saves to `weights/bert_review_sentiment_epoch_NN.pt`, then a separate cell saves the final model to `models/bert_review_sentiment/`) | `models.load_fine_tuned_bert()` loads the verified `save_pretrained()` directory |
| Ambiguous variable names | Checks generic `model`/`tokenizer` names that could resolve to the Marian translation model/tokenizer loaded earlier in the same notebook session | Explicit `bert_model`/`bert_tokenizer` returned from a dedicated loader; the CNN path uses its own `cnn_model`/`cnn_tokenizer` |
| Untrained fallback | On load failure, falls back to a FRESH `AutoModelForSequenceClassification.from_pretrained(BERT_CHECKPOINT, num_labels=2)` — a randomly-initialized classification head — and would silently serve untrained predictions | `load_fine_tuned_bert()` raises `FileNotFoundError`/`RuntimeError` instead; `ModelRegistry` marks the artifact `loading_failed` and the API returns HTTP 503, never a prediction |
| **Actually crashed in the notebook** | The captured cell-149 output shows the primary load attempt failed (`ignore_mismatched_sizes` not set), the fallback ALSO attempted with `ignore_mismatched_sizes=False` by default, and raised an uncaught `RuntimeError` — the notebook's own inference cell does not run cleanly as written | N/A — documented as evidence this exact pattern must not be reproduced |

## 7. Raw dataset availability

The 9 raw Olist CSVs are **not present** in the originally uploaded `update/` folder, but WERE located at `Fake news/E-commerce/Dataset/` — the exact directory the notebook's own `MANUAL_BASE_PATH` hard-coded (`r"C:\Users\User1\Downloads\Fake news\E-commerce\Dataset"`), confirming this is genuinely the source data the notebook was built against. All 9 files pass `data_loading.validate_olist_schema()` with zero missing columns. They are included in this delivery under `data/raw/`, and `data/processed/*.parquet` + every `results/*.json` file were regenerated for real from them via `run_pipeline.py --clean --eda --segment` — not derived from the notebook's own already-lossy export. This surfaced two real bugs (both fixed, both regression-tested):

1. **`build_reviews_enriched` crashed on genuine raw data**: the raw reviews CSV has 827 duplicate `review_id` rows (invisible to the notebook's own exact-full-row duplicate check). Fixed by deduplicating on `review_id` before the uniqueness assertion.
2. **Order-status undercounting via the item-join path**: 775 orders have no matching `order_items` row and were silently dropped by the notebook's `dropna(subset=["product_id"])`, disproportionately hiding `canceled`/`unavailable` orders (true count 625/609 vs. the item-joined path's 461/6). `orders_enriched` — built without ever joining through `items` — does not have this blind spot. Full detail: `DATA_GRAIN_AUDIT.md` §5–6.

## 8. End-to-end verification performed

- CNN2D checkpoint: `strict=True` load — **passed**.
- BERT directory: `from_pretrained()` load, `num_labels==2`, `id2label` check — **passed**.
- CNN tokenizer: unpickled, vocab size verified against notebook output — **passed**.
- Real BERT inference via CLI (`inference.py --text "..." --model bert`) — **passed**, correct Positive/Negative predictions, deterministic on repeat, probabilities sum to 1.0.
- Real CNN2D inference via CLI — **passed** (positive/negative/OOV-heavy inputs all produced valid, bounded probabilities).
- Live FastAPI server: `/api/v1/health`, `/api/v1/models/status`, `/api/v1/sentiment/predict`, `/api/v1/analytics/summary`, `/api/v1/segmentation/predict` — all **passed** with real model-backed responses (see API_DOCUMENTATION.md for full transcript).
- Live React frontend against the live backend: Dashboard KPI cards and charts render real numbers (initially 98,666 unique orders derived from the notebook's own lossy export; re-verified via direct API call after switching to the genuine raw-CSV pipeline: **99,441 unique orders, R$15,422,462 delivered revenue**); Sentiment page submits a real review and displays a real BERT prediction (99.9% Positive) — **passed**, verified via browser automation and a follow-up live API re-check.
- `pytest`: **47 passed, 0 failed, 0 skipped** (all artifacts were present in this environment, so no test needed to skip; includes a regression test for the duplicate-`review_id` bug found and fixed during raw-data verification).

## 9. Remaining limitations / requires-user-action

| Item | Status |
|---|---|
| Raw 9 Olist CSVs | **Present** under `data/raw/` (located at `Fake news/E-commerce/Dataset/`); `run_pipeline.py --clean --eda --segment` has been run against them for real in this delivery |
| Retraining BERT/CNN2D on the corrected split | Not run in this delivery (would take ~30+ min CPU for BERT); `train.py` implements it and is ready to run |
| SHAP explainability | `shap` package not installed in the verification environment; `explainability.py` degrades gracefully and reports `available: false` rather than crashing — install `shap` to enable |
| Fake-review / ABSA modules | Require downloading external HF models (`jb10231/fake-review-detector`, `yangheng/deberta-v3-base-absa-v1.1`); not downloaded in this delivery (`ALLOW_EXTERNAL_MODEL_DOWNLOADS=false` by default) |
| Docker build | `docker compose config` validated successfully (both services resolve correctly, ports/env/build args all correct). `docker compose build` could not complete in this session — the Docker CLI is present (v29.1.3) but the daemon requires elevated privileges not available in this sandboxed session ("must be run with elevated privileges to connect"). Run `docker compose build && docker compose up` yourself with normal Docker Desktop permissions to build the images. |
