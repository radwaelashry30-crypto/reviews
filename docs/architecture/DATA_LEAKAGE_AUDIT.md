# Data Leakage Audit

## 1. What the original notebook did

`olist_full_eda_preprocessing_PYTORCH.ipynb`, section 8 ("Dataset Splitting"):

1. Cell 119 builds `bert_df` (38,062 rows after the score/text filter) and performs a stratified 70/10/20 split via `train_test_split`, producing `X_train`/`X_val`/`X_test` (26,642 / 3,807 / 7,613 rows).
2. Cell 120 runs a leakage check on that split and reports:
   - Index overlap: 0 across all pairs (expected — `train_test_split` never duplicates rows).
   - **Duplicate raw-text overlap: Train∩Val = 339, Train∩Test = 552, Val∩Test = 206 → 1,097 total identical review texts shared across splits.**
3. Cell 121 rebuilds `bert_df` and calls `bert_df.drop_duplicates(subset=["text"])`, reducing it to 31,846 unique rows — but **`X_train`, `X_val`, `X_test`, `y_train`, `y_val`, `y_test` from cell 119 are never regenerated from this deduplicated frame.** All downstream training and evaluation (BERT cells 124–136, CNN2D cells 129–138) continues to use the ORIGINAL, leakage-containing split objects from cell 119.

**Conclusion: the notebook's reported BERT/CNN2D metrics (`results/notebook_reported_metrics.json`) were computed on a test set that shares 552+206=758 (test-side) identical review texts with the train/val data the models were fit on. These metrics are optimistically biased and are NOT leakage-free.**

## 2. Corrected pipeline (this project)

Implemented in `backend/app/ml/preprocessing.py` (`normalize_review_text`, `remove_duplicate_reviews`, `resolve_conflicting_labels`, `split_sentiment_dataset`) and run via `backend/scripts/train.py` / the verification script that produced `results/reproduced_metrics.json`.

Steps, in order:
1. Build the labeled frame exactly as the notebook does (score ∈ {1,2,4,5}, non-"No Message", non-empty translated text).
2. **Normalize** each text (lowercase + collapsed whitespace) — catches near-duplicates that differ only in casing/whitespace, which exact-string `drop_duplicates` misses.
3. **Resolve conflicting labels**: group by normalized text; where the same text appears with both a Negative and a Positive label (unresolvable from text alone), drop every row in that group.
4. **Drop duplicate normalized text**, keeping the first occurrence.
5. **Only then** perform the stratified 70/10/20 split (`random_state=42`).
6. Save every split's `review_id` + `text_hash` + `label` to `artifacts/split_manifest.json` so evaluation/inference can reuse the exact same rows.

## 3. Verified results (run against `data/interim/reviews_translated.csv`, 2026-08-04)

| Metric | Value |
|---|---|
| Rows before dedup (score+text filter applied) | 38,060 |
| Duplicate-text groups found | 1,215 |
| Conflicting-label groups found | 76 |
| Rows dropped for conflicting labels | 2,381 |
| Rows after full dedup | 31,484 |
| Corrected split sizes (train/val/test) | 22,038 / 3,149 / 6,297 |

(The 38,060 vs. the notebook's reported 38,062, and 31,484 vs. the notebook's 31,846, differ slightly because this project's translation cache has 41,723 non-empty translated rows vs. the notebook run's 41,725 — a 2-row difference from the translation pipeline's own per-batch failure handling, which is expected to vary slightly across runs of a network-free but hardware/timing-sensitive batch process. The larger 31,484 vs 31,846 gap is expected and correct: this pipeline additionally normalizes text before dedup and removes conflicting-label duplicates, which the notebook's raw `drop_duplicates` did not do.)

### Overlap verification on the corrected split

| Check | Train∩Val | Train∩Test | Val∩Test |
|---|---|---|---|
| Row-index overlap | 0 | 0 | 0 |
| Raw-text overlap | 0 | 0 | 0 |
| Normalized-text overlap | 0 | 0 | 0 |

All zero, confirmed by `SplitResult.overlap_report()` in `preprocessing.py` and re-verified in `backend/app/tests/test_preprocessing.py::test_split_has_no_text_overlap`.

## 4. Was the original notebook affected?

Yes. `results/notebook_reported_metrics.json` reflects the ORIGINAL, leaky split and is preserved as-is (never overwritten) for transparency. `results/reproduced_metrics.json` reflects the corrected split and is the number this project recommends citing.

## 5. Reproducibility

- Fixed seed: 42, used for both the deduplication-aware split and (separately) model initialization.
- Tokenizers (BERT's own subword tokenizer, and the CNN's `SimpleVocabTokenizer`) are fit ONLY on the corrected TRAIN partition — see `train.py`'s `cnn_tokenizer.fit_on_texts(split.train["text"])`.
- The split manifest (`artifacts/split_manifest.json`) stores stable identifiers (`review_id`, `text_hash`) rather than positional indices, so `evaluate.py` can always reconstruct the exact same test set independent of re-running the split.
