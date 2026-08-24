# Model Card — Baseera

## Overview

Baseera runs two independently trained binary sentiment classifiers over Olist marketplace reviews (translated Portuguese → English), plus an optional, explicitly experimental module layered on top: aspect-based sentiment (ABSA).

| Model | Role | Params | Test accuracy | Deployed where |
|---|---|---:|---:|---|
| Fine-tuned BERT (`LiYuan/amazon-review-sentiment-analysis` base) | Primary sentiment classifier | ~178M | 93.70% | Locally / hosts with ≥1GB RAM |
| CNN2D (from-scratch, bag-of-n-grams) | Fallback sentiment classifier | ~3.0M | 92.01% | Live production (Render, 512MB RAM) |
| CNN2D + RAKE clause localization | Aspect-based sentiment (Task 2) | reuses CNN2D above, 0 extra | inherits CNN2D's 92.01%, no separate ABSA benchmark | Live production (zero extra RAM cost) |

## Task and label mapping

Binary sentiment: **1–2 stars → Negative (0), 4–5 stars → Positive (1)**. 3-star and textless reviews are excluded from training/evaluation. Predictions are probabilistic estimates over this specific dataset, not objective ground truth about a customer's actual experience.

## Training data

Olist Brazilian e-commerce reviews (Jan 2017–Aug 2018), machine-translated to English (MarianMT). 22,038 train / 3,149 val / 6,297 test after deduplication and leakage-safe splitting — see `DATA_LEAKAGE_AUDIT.md` and `DATA_QUALITY_AUDIT.md` for the full data pipeline audit.

## Evaluation

Full metrics: `MODEL_COMPARISON_AUDIT.md`. Headline numbers are computed on the untouched test split, never used for training, tuning, or threshold selection. Threshold (0.5) and calibration were independently checked on the validation split (`MODEL_COMPARISON_AUDIT.md` §8, `results/calibration_analysis.json`):

- **BERT**: 0.5 is the accuracy/F1-optimal threshold across a 0.30–0.70 sweep. Brier score 0.0502, ECE 0.0309 (well-calibrated).
- **CNN2D**: 0.5 is within 0.15 percentage points of the sweep optimum (t=0.45) — not a meaningful miscalibration. Brier score 0.0673, ECE 0.0597 (reasonably calibrated, worse than BERT).

## Known, confirmed limitations

- **CNN2D cannot reliably handle negation** ("the product is not bad" → misclassified Negative). Architectural ceiling for a small bag-of-n-grams model — two augmented-retraining attempts at increasing data scale did not close the gap (`MODEL_COMPARISON_AUDIT.md` §5–6). BERT handles this correctly; CNN2D is what the public deployment currently serves due to RAM constraints.
- **BERT had a blind spot on blunt delivery-lateness complaints** ("the shipment coming late" → 99.5% Positive). Attempted a fix via targeted continued fine-tuning (§7). The originally reported "11.1% → 1.0%" false-positive-rate improvement was measured incorrectly (on the full dataset, including rows the model had just trained on, not a held-out set) and has been corrected: on the test split only (94 genuinely-negative delay rows), the honest before/after is 3.2% → 5.3%, not a statistically significant change at that sample size. The augmentation does not regress overall test-set accuracy, but does not demonstrably fix this specific blind spot either — see `results/bert_late_delivery_augmentation_report.json`. This checkpoint lives locally only; the public deployment serves CNN2D, which did not have this specific bug.
- **ABSA (Task 2) previously hallucinated aspects never mentioned in the text** — fixed via a keyword-presence gate; unmentioned aspects now report "Not mentioned" instead of a guessed sentiment. The original ~738MB external ABSA model was later replaced entirely with CNN2D scoring the RAKE-located clause for each aspect (zero extra memory, zero new dependencies, evaluated against two smaller external alternatives that were both rejected — one for a hidden TensorFlow dependency, one for being unverified). Tradeoff: no "Neutral" class, and clause-level sentiment approximates aspect-level sentiment rather than a purpose-trained model. See module docstring in `backend/app/ml/absa.py`.
- **RFM segmentation's Frequency dimension is nearly constant for this dataset.** ~97% of Olist customers placed exactly one order, so `Frequency` carries almost no variance and contributes little real signal to the clustering beyond Recency and Monetary. This is a property of the dataset (most Olist customers genuinely are one-time buyers in this window), not a bug, but it means segment separation is effectively driven by Recency and Monetary alone -- a richer repeat-purchase signal (e.g. `days_since_first_order`, `avg_order_value`) would likely produce more informative segments than adding more weight to `Frequency` itself. Not changed here since it would alter the feature set and downstream API contract; flagged as a known limitation instead of left implicit.

## Intended use / responsible-use statement

Do not use sentiment predictions to make consequential decisions about individual customers or sellers without human review. Do not present the ABSA module's output as validated ground truth — it carries explicit reliability caveats in its API response.

## Reproducibility

Seed 42 throughout (dataset split, class weights, PyTorch/NumPy/Python RNG). Tokenizers fit on the training split only. Full training/evaluation commands: `README.md` §30–31. Retraining scripts for the confirmed fixes above: `backend/scripts/retrain_cnn2d_negation_augmented.py`, `backend/scripts/retrain_bert_late_delivery_augmented.py`.
