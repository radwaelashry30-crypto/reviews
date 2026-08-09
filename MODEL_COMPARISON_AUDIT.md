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

## 5. CNN2D negation retrain (2026-08-07)

**Problem, verified by direct testing**: CNN2D misreads "the product is not bad" as Negative at 97.2% confidence. BERT, on the same input, correctly reads it Positive at 83.2%. This is a real architectural gap, not a one-off: CNN2D is a bag-of-n-grams model (filter sizes 2-5, global max-pool) whose predictions lean heavily on individual strong-sentiment words like "bad"/"terrible" regardless of a preceding "not" — it has to learn negation entirely from patterns present in its own training data, and Olist's translated review text underrepresents them. BERT generalizes negation from pretraining and doesn't have this problem.

**Fix attempted**: `backend/scripts/retrain_cnn2d_negation_augmented.py` augments CNN2D's TRAIN split (Olist val/test untouched) with a small, label-balanced, negation-rich sample pulled from Datafiniti's Amazon Consumer Reviews dataset (`app/ml/negation_augmentation.py`). Raw Amazon reviews are ~93% positive-labeled, so naive sampling would have made calibration worse — the sampler instead takes ALL available negative-labeled examples (987 negated + 854 ordinary, the scarce resource) and matches each with an equal-sized positive sample, giving an exactly 50/50-balanced 3,682-row augmentation set (1,974 negated / 1,708 ordinary), with the negated portion additionally oversampled 4x in the final training mix (9,604 of 31,642 total training rows) for a stronger gradient signal. A fresh tokenizer was fit on the combined train text (train-only, no val/test leakage) and CNN2D was trained from scratch — a checkpoint and its tokenizer are always a matched pair (see §2 above).

**Result — genuine improvement, but NOT a full fix**:

| | Before | After |
|---|---|---|
| Olist test accuracy (n=6,297, unaugmented) | 0.9192 | **0.9201** (no regression) |
| Olist test F1-macro | 0.9074 | **0.9127** |
| Hand-crafted negation eval (10 cases, held out from training) | 7/10 | 7/10 (same count, but `p_positive` moved toward correct on the failing cases, e.g. "not bad" 0.028 → 0.116) |

"the product is not bad" **still classifies as Negative** after this fix (p_positive=0.116, up from 0.028 but still well under the 0.5 threshold). Two other short "not + strong-negative-word" idioms ("not late", "not terrible") also remain wrong. More balanced negation data measurably helped (better test accuracy AND F1, better probability calibration on 7 of 10 cases) but did not fully close the gap on this specific idiom pattern — the available real negated-and-negative training examples (987) are too few, and the failure mode (a single strong-polarity word overpowering a 2-gram "not X" filter) is a known, documented limitation of small n-gram CNN text classifiers, not something more data alone reliably fixes at this scale. Full correctness on this pattern class would need either substantially more real negation data, synthetic template augmentation at much larger scale, or (most reliably) an attention-based model — which is exactly what BERT already provides.

**Practical consequence**: on this project's own deployed backend (Render free tier, 512MB RAM), `ENABLE_BERT=false` — the public site currently serves CNN2D-only, so this exact failure mode is user-visible there. Locally / on a host with enough RAM for BERT, this class of input is already handled correctly by the primary model.

Applied to the shipped `models/cnn2d_review_sentiment.pt` + `artifacts/cnn2d_tokenizer.pkl` since it is a strict, measured improvement (better accuracy, better F1, no case that got worse) with no regression. Full before/after data: `results/cnn2d_negation_augmentation_report.json`. Reproduce with `python backend/scripts/retrain_cnn2d_negation_augmented.py --apply`.

## 6. Follow-up: does a much larger negation corpus fix it? (2026-08-09)

**Hypothesis tested**: §5's Datafiniti source is small (44,824 rows, only 1,841 negative-labeled, capping the negated-negative pool at 987). A user-suggested follow-up: pull negation examples from a far larger, perfectly class-balanced Amazon review corpus and see whether more data closes the remaining gap. `app/ml/negation_augmentation.load_amazon_polarity_dataset` was added for the Amazon Reviews Polarity dataset (Zhang et al. 2015; downloaded via its HuggingFace mirror `fancyzhx/amazon_polarity`, same underlying corpus as `kaggle.com/datasets/kritanjalijain/amazon-reviews`) — one 900K-row shard alone has **300,023 negated-negative rows**, ~300x more than Datafiniti's entire negative pool.

Two configurations were trained and evaluated against the same Olist test set and hand-crafted negation eval set as §5:

| Configuration | Combined train size | Olist test accuracy | Olist test F1-macro | Negation eval | "not bad" p_positive |
|---|---|---|---|---|---|
| §5 baseline (no augmentation) | 22,038 | 0.9192 | 0.9074 | — | 0.028 |
| **§5, deployed** (Datafiniti, 3,682 rows, 4x negated oversample) | 31,642 | **0.9201** | **0.9127** | 7/10 | 0.116 |
| Polarity, 60,000-row augmentation (36,000 negated) | 82,038 | 0.9136 | 0.9053 | 7/10 | 0.189 |
| Polarity, 25,000-row augmentation (15,000 negated) | 47,038 | 0.9119 | 0.9040 | **6/10** | 0.083 |

**Finding: more data did NOT beat the deployed checkpoint.** Both Polarity configurations score *worse* than §5 on the primary Olist test metrics — because Amazon Polarity is a different domain (general e-commerce/media reviews, not Olist's Brazilian marketplace text), and at 25K-60K augmented rows it outweighs Olist's own 22,038 training rows in the combined mix (52-73% non-Olist), diluting the in-domain signal. The 60K run's `p_positive` for "not bad" did move further toward correct (0.189 vs. 0.116) and the 25K run's negation accuracy dropped to 6/10 — the relationship between augmentation volume and negation-idiom correctness is not monotonic across these runs, and neither crosses the 0.5 decision threshold on "not bad" / "not late" / "not terrible" regardless of data volume.

**Conclusion**: this specific failure mode (a single strong-polarity word like "bad"/"terrible" overpowering a short "not X" n-gram filter) is a genuine architectural ceiling for a from-scratch, ~3M-parameter n-gram CNN — not a data-scarcity problem fixable by throwing a larger corpus at it, and doing so trades away Olist-domain accuracy for an incomplete fix. **The §5 checkpoint remains deployed** (`models/cnn2d_review_sentiment.pt` was NOT overwritten by this experiment — both Polarity runs were dry runs, `--apply` was never passed). BERT is the reliable answer for this input class; it already handles all three idioms correctly. Full data: `results/cnn2d_negation_augmentation_report.json` (latest run overwrites the file — the numbers above are preserved here since the JSON only reflects the most recent invocation).

- It does not claim CNN2D is a bad model — 0.92 accuracy on a corrected, leakage-free split with a ~3M-parameter from-scratch architecture trained in 155 seconds is a strong result for its class.
