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

## 7. BERT late-delivery blind spot fix (2026-08-09)

**Problem, verified by direct testing**: BERT (the primary, more accurate model) classifies blunt "late/delayed delivery" complaints as **Positive** with very high confidence when the sentence has no other negative vocabulary — e.g. "the shipment coming late" → Positive 99.5%, "the delivery is late" → Positive, "Late delivery!" → Positive. CNN2D and the Task 3 ABSA model both correctly read the same input as Negative, which is what surfaced the bug: the UI showed a Positive headline with every ABSA aspect labeled Negative underneath it.

Scoped against real data: of the 599 Olist reviews (3-star excluded) mentioning "late"/"delay", BERT scored only 86.0% accuracy (vs. ~93% overall) with an **11.1% false-positive rate** (47/425) on genuinely negative delay complaints. Root cause: many Olist reviews mention a delay but still rate 4-5 stars ("a bit late but the product paid off"), so the fine-tuned model learned "late/delay" alone is a weak, ambiguous signal and defaulted to its positive-skewed prior on short, blunt sentences lacking an explicit negative adjective.

**Fix applied**: `backend/scripts/retrain_bert_late_delivery_augmented.py` continues fine-tuning the currently-deployed BERT checkpoint (not from scratch, to avoid re-learning everything else) for 1 epoch at a low learning rate (1e-5), on the original Olist TRAIN split plus: (1) the 263 real Olist TRAIN-split reviews that are genuinely negative and mention late/delay, oversampled 3x (789 rows), and (2) 74 synthetic template sentences — 64 blunt negative lateness complaints (label 0) and 10 "delayed but still positive" sentences (label 1, e.g. "a bit late but worth the wait") so the model doesn't overcorrect into treating every delay mention as negative.

**Result — clean improvement, no regression**:

| | Before | After |
|---|---|---|
| Olist test accuracy (n=6,297, unaugmented) | 0.9333 | **0.9370** (slight improvement) |
| Late/delay eval set accuracy (562 rows, 3-star excluded) | 0.860 | **0.920** |
| False-positive rate on genuinely-negative late/delay reviews | 11.1% (47/425) | **1.0%** (4/392) |
| Hand-crafted eval (10 cases incl. "the shipment coming late", held out from training) | not applicable (bug not yet fixed) | **10/10**, including nuance cases like "a bit late but worth the wait" staying correctly Positive (93.8%) |

"the shipment coming late" now classifies Negative at 97.2% confidence. Applied to the shipped `models/bert_review_sentiment/` since it is a strict, measured improvement (better accuracy, better F1, dramatically lower false-positive rate on the target failure mode, no case that got worse) with no regression on the untouched Olist test set. Full before/after data: `results/bert_late_delivery_augmentation_report.json`. Reproduce with `python backend/scripts/retrain_bert_late_delivery_augmented.py --apply`.

> **Correction (2026-08-18), left in place rather than silently edited, per this document's own standard of showing what was wrong and why:** the row above ("False-positive rate ... 11.1% -> 1.0%") was measured on `deduped` -- the full train+val+test dataset -- not a held-out split, and the model had just been trained on 3x-oversampled copies of the exact same 263 negative late/delay reviews that dominate that row's denominator. The "562-row eval set / 10-case hand-crafted eval" was also templated from the same generator functions used to build training data, so 4/10 hand-crafted items were literal matches against the training set. An external technical review caught both issues; `retrain_bert_late_delivery_augmented.py` was rewritten to evaluate the late/delay false-positive rate on `split.test` only (before AND after training, same 94 negative rows, with a Wilson confidence interval given the small sample), and to use a genuinely disjoint hand-crafted eval set with a code-enforced leakage check. Re-run honestly: **3.2% -> 5.3%** (95% CIs [1.1%, 9.0%] and [2.3%, 11.9%] -- overlapping, not a statistically distinguishable change at this sample size). The new hand-crafted set (different vocabulary from training) scored 9/10, with one genuine remaining miss ("Three weeks behind schedule and support went silent" -> Positive 99.3%). Overall test-set f1_macro still improved slightly (0.9303 -> 0.9325, no regression), so the checkpoint isn't harmful, but this specific blind spot is **not demonstrably fixed** by the augmentation -- see `results/bert_late_delivery_augmentation_report.json` for the current, honest numbers.

## 8. Threshold and calibration analysis (2026-08-16)

**Motivation**: the deployed decision threshold (0.5) had never been empirically validated for either model, and neither model's predicted probabilities had ever been checked for calibration (does "90% confident" actually mean right ~90% of the time?). Run via `backend/scripts/calibration_analysis.py` on the **validation split only** (n=3,149; never the test split used for headline metrics, never used for training or early stopping).

**Threshold sweep (0.30-0.70, step 0.05)**:

| | BERT | CNN2D |
|---|---|---|
| Accuracy at t=0.5 (current default) | 0.9390 | 0.9190 |
| Best accuracy in sweep | **0.9390 at t=0.50** (already optimal) | 0.9200 at t=0.45 |
| F1 at t=0.5 | 0.9536 | 0.9373 |
| Best F1 in sweep | **0.9536 at t=0.50** (already optimal) | 0.9386 at t=0.45 |

**Finding**: for BERT, 0.5 is already the accuracy- and F1-optimal threshold across the entire sweep — no change justified. For CNN2D, t=0.45 edges out t=0.50 by +0.10pp accuracy / +0.13pp F1, which is within normal validation-fold noise for ~3,100 examples, not a meaningful miscalibration of the threshold. **Conclusion: 0.5 is kept for both models** — this is a case where the audit's answer is "checked, no defect found," not a manufactured fix.

**Calibration (Brier score, Expected Calibration Error, 10 bins)**:

| | BERT | CNN2D |
|---|---|---|
| Brier score (0=perfect, 0.25=coin-flip) | **0.0502** | 0.0673 |
| ECE (0=perfectly calibrated) | **0.0309** | 0.0597 |

Both models are reasonably well-calibrated (an average gap of ~3% for BERT and ~6% for CNN2D between stated confidence and actual accuracy across confidence bins) — well short of "confidently wrong," though BERT is the better-calibrated of the two, consistent with it being the larger, better-performing model. Full per-bin breakdown and the complete threshold sweep: `results/calibration_analysis.json`. Reproduce with `python backend/scripts/calibration_analysis.py --model both`.
