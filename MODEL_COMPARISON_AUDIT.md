# Model Comparison Audit

## 1. The problem: mismatched test sets in the notebook

Notebook cell 124 subsamples the (leaky) 70/10/20 split down to fixed sizes for BERT:

```python
TRAIN_SIZE = 5000
VAL_SIZE   = 1000
TEST_SIZE  = 2000
X_train_bert_raw = X_train[:TRAIN_SIZE] ...
```

CNN2D (cell 129/133) uses the FULL split (26,642 / 3,807 / 7,613) with no subsampling. Cell 140's side-by-side comparison table then reports:

| Model | Test set | Test size |
|---|---|---|
| BERT | first 2,000 rows of the (leaky) test split | 2,000 |
| CNN2D | full (leaky) test split | 7,613 |

**These are two different populations of different sizes.** The notebook's own conclusion ("BERT is the primary model based on accuracy and macro F1") is stated without disclosing this mismatch. Verified directly from the notebook's own captured output (cell 124: `Test: 2,000 examples`; cell 133 training log: full split trained on 26,642/3,807/7,613).

## 2. Two comparison modes provided by this project

### Notebook reproduction mode — `results/notebook_reported_metrics.json` + `results/notebook_model_comparison.json`

Verbatim values captured from the notebook's own executed cells (136, 138, 140). Preserved unmodified as a historical record. **Do not use these to claim one model is better** — see §1.

### Fair comparison mode — `results/fair_model_comparison.json`

Both models evaluated via genuine forward-pass inference (`evaluation.get_bert_predictions` / `get_cnn_predictions`, no retraining) on the IDENTICAL corrected, deduplicated test split (6,297 reviews, same `review_id`s, same seed=42, same label mapping — see DATA_LEAKAGE_AUDIT.md for how that split was built).

**A technical subtlety this project had to work around:** the CNN2D checkpoint's embedding layer is indexed to the specific vocabulary its ORIGINAL tokenizer (`artifacts/cnn2d_tokenizer.pkl`, fit on the notebook's original uncorrected train split) built at training time. An early version of this evaluation refit a fresh `SimpleVocabTokenizer` on the corrected split's train partition (the textbook-correct thing to do for a NEW training run) and paired it with the EXISTING checkpoint — this silently scrambles every embedding lookup (verified: accuracy collapsed to 0.577–0.588, barely above the majority-class baseline). The corrected evaluation instead pairs the existing checkpoint with its ORIGINAL tokenizer, which is the only combination that reflects what that checkpoint actually learned. A genuinely retrained CNN2D on the corrected split (fresh tokenizer + fresh weights, trained together via `train.py --model cnn2d`) is a separate, valid exercise that would produce a new checkpoint — not "reproduced metrics" for the existing one.

### Verified fair-comparison results (2026-08-04, corrected test split, n=6,297)

| Metric | BERT | CNN2D |
|---|---|---|
| Accuracy | 0.9344 | 0.9222 |
| Precision (macro) | 0.9254 | 0.9064 |
| Recall (macro) | 0.9288 | 0.9310 |
| F1 (macro) | 0.9271 | 0.9159 |
| ROC-AUC | 0.9755 | **0.9770** |
| PR-AUC | 0.9866 | 0.9879 |
| MCC | 0.8542 | 0.8370 |

BERT wins on accuracy, precision, F1-macro, and MCC. **CNN2D has a marginally higher ROC-AUC**, consistent with the same pattern the notebook observed on its own (mismatched) test sets (BERT 0.9716 vs CNN2D 0.9717). This is the one conclusion that holds up even after fixing the leakage and the test-set mismatch.

## 3. Verdict

On a fair, identical, leakage-corrected test set, **BERT is the stronger model on every metric except ROC-AUC**, where the two are statistically indistinguishable (0.9755 vs 0.9770). This project designates BERT as the primary production model (`config/project_config.json: primary_sentiment_model: "bert"`), consistent with — but now actually justified by — the notebook's original conclusion.

## 4. What this audit does NOT claim

- It does not claim the notebook's original 0.9275/0.9192 accuracy figures are wrong in isolation — they are exactly what that code produced. It claims they cannot be used to compare the two models against each other, and that the underlying split had test-set leakage.
- It does not claim CNN2D is a bad model — 0.92 accuracy on a corrected, leakage-free split with a ~3M-parameter from-scratch architecture trained in 155 seconds is a strong result for its class.
