"""Continues fine-tuning the deployed BERT checkpoint to fix a verified blind
spot: blunt "late/delayed delivery" complaints with no other negative
vocabulary (e.g. "the shipment coming late", "the delivery is late") get
classified Positive with >95% confidence, while CNN2D and the ABSA aspect
model both correctly read them as Negative.

Measured on 599 real Olist reviews mentioning late/delay (3-star excluded):
BERT scores 86.0% accuracy but has an 11.1% false-positive rate on genuinely
negative delay complaints (47/425) -- e.g. "Late delivery!", "The delivery is
late." classified Positive. Likely cause: many Olist reviews mention a delay
but still rate 4-5 stars ("a bit late but the product paid off"), so the
fine-tuned model learned "late/delay" alone is a weak/ambiguous signal, and
defaults to its (heavily positive-skewed) prior on short bare sentences.

Fix strategy: CONTINUE fine-tuning from the currently-deployed checkpoint
(not from the base LiYuan checkpoint -- avoids re-learning everything else)
for a small number of epochs at a low learning rate, on the original TRAIN
split plus:
  1. Real Olist TRAIN-split reviews that are genuinely negative (label 0)
     and mention late/delay, oversampled.
  2. A small set of synthetic, clearly-labeled template sentences: blunt
     negative lateness complaints (label 0) AND "delayed but still positive"
     sentences (label 1), so the model doesn't overcorrect into treating
     every delay mention as negative -- Olist's real data shows ~29% of
     delay-mentioning reviews genuinely are positive.

**Evaluation integrity, fixed after a real audit finding**: an earlier
version of this script evaluated the "false positive rate reduction" claim
on `deduped` (the FULL train+val+test dataset) rather than the held-out test
split, while the model had just been trained on 3x-oversampled copies of the
exact same negative late/delay reviews from the train split -- so the
headline "11.1% -> 1.0%" number was measured partly on data the model had
just memorized. It also had a hand-crafted "held out" eval set that was
templated from the SAME generator functions used to build training data,
so 4/10 of its items were literal string matches against the training set.
Both are fixed here: the late/delay eval set is now built from split.test
only, evaluated before AND after training (baseline vs new, same rows), with
a Wilson confidence interval given the small sample size; the hand-crafted
eval set uses entirely different vocabulary/phrasing than the training
templates, and its disjointness from the training set is asserted in code,
not just by inspection.

Evaluated on: the full untouched Olist test split (must not regress) and the
late/delay-mentioning subset of the test split (must reduce the false-positive
rate, compared honestly against the pre-training baseline on identical rows).

Usage:
    python scripts/retrain_bert_late_delivery_augmented.py --apply
        (without --apply, evaluates and reports but does not overwrite the
        shipped models/bert_review_sentiment/ checkpoint. --apply itself
        refuses to overwrite if the new checkpoint regresses on the Olist
        test set beyond REGRESSION_TOLERANCE.)
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml import datasets as ds, evaluation as ev, models as ml_models, preprocessing as prep  # noqa: E402
from app.ml.preprocessing import normalize_review_text  # noqa: E402
from app.ml.training import run_bert_epoch  # noqa: E402
from app.ml.utils import checkpoint_fingerprint, get_device, set_seed, write_json  # noqa: E402

LATE_DELAY_PATTERN = r"\blate\b|\bdelay"
REGRESSION_TOLERANCE = 0.002  # acceptable noise margin on f1_macro

SUBJECTS = ["the shipment", "the delivery", "the package", "the order", "the product", "the item", "the parcel", "shipping"]
NEG_PREDICATES = ["coming late", "came late", "is late", "was late", "arrived late", "is delayed", "was delayed", "got delayed"]
POS_TEMPLATES = [
    "the delivery was late but the product is excellent",
    "shipment was late but everything arrived perfect",
    "a bit late but worth the wait",
    "delayed delivery but great product overall",
    "late but the quality made up for it",
    "the order was delayed but I still loved it",
    "a small delay in delivery, but the product is amazing",
    "shipping took a while but the item is fantastic",
    "yes it came late, but honestly worth it",
    "despite the delay, excellent product and I recommend it",
]

# Genuinely held out: different verbs, subjects and sentence structure than
# SUBJECTS/NEG_PREDICATES/POS_TEMPLATES above, so this measures generalization
# rather than template memorization. Verified disjoint from the training set
# in code by assert_eval_is_held_out() below, not just by inspection.
NEGATION_EVAL_SET = [
    ("It took forever to show up, way past the estimate.", 0),
    ("Still waiting after three weeks, this is unacceptable.", 0),
    ("My order hasn't turned up yet and no one can tell me why.", 0),
    ("Ridiculous how long this took to reach me.", 0),
    ("Courier kept pushing the date back, very frustrating experience.", 0),
    ("Three weeks behind schedule and support went silent.", 0),
    ("Took ages to arrive, but I'm genuinely happy with what I got.", 1),
    ("Waited longer than expected, no complaints about the item itself though.", 1),
    ("Everything showed up right on schedule and works great.", 1),
    ("Super fast, exactly as promised, no issues at all.", 1),
]


def assert_eval_is_held_out(synthetic_df: pd.DataFrame, real_train: pd.Series, eval_set: list[tuple[str, int]]) -> None:
    """Fails the script loudly if any hand-crafted eval item is a literal
    (normalized) match against anything the model is about to be trained on
    -- no room for a silent, unnoticed repeat of the leakage this replaced."""
    train_norm = {normalize_review_text(t) for t in pd.concat([synthetic_df["text"], real_train], ignore_index=True)}
    leaked = [t for t, _ in eval_set if normalize_review_text(t) in train_norm]
    if leaked:
        raise RuntimeError(f"Eval leakage: {len(leaked)}/{len(eval_set)} eval items are in train: {leaked}")


def wilson_confint(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion -- appropriate
    here because the late/delay-mentioning test subset is small enough that
    a raw point estimate alone is misleading (see Technical Review #02)."""
    if n == 0:
        return 0.0, 0.0
    phat = successes / n
    denom = 1 + z**2 / n
    center = phat + z**2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    return ((center - margin) / denom, (center + margin) / denom)


def build_synthetic_examples() -> pd.DataFrame:
    negatives = [f"{subj} {pred}" for subj, pred in itertools.product(SUBJECTS, NEG_PREDICATES)]
    rows = [{"text": t, "label": 0} for t in negatives] + [{"text": t, "label": 1} for t in POS_TEMPLATES]
    return pd.DataFrame(rows)


@torch.no_grad()
def late_delay_fp_rate(model, texts: pd.Series, labels: pd.Series, tokenizer, device, max_len: int, batch_size: int) -> tuple[float, int, int]:
    """Returns (fp_rate, n_false_positives, n_negatives) for genuinely
    negative (label 0) rows in `texts`/`labels`."""
    loader = ds.build_bert_dataloader(texts.tolist(), labels.tolist(), tokenizer, max_len, batch_size, shuffle=False)
    y_true, y_pred, _ = ev.get_bert_predictions(model, loader)
    fp_mask = (y_true == 0) & (y_pred == 1)
    n_negatives = int((y_true == 0).sum())
    return float(fp_mask.sum()) / max(1, n_negatives), int(fp_mask.sum()), n_negatives


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--negative-oversample", type=int, default=3, help="Repeat the real Olist TRAIN-split negative late/delay reviews this many times.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--apply", action="store_true", help="Overwrite models/bert_review_sentiment/ if the new checkpoint doesn't regress on the Olist test set.")
    parser.add_argument("--force", action="store_true", help="With --apply, overwrite even if the new checkpoint regressed on the Olist test set.")
    args = parser.parse_args()

    set_seed(args.seed)
    device = get_device()
    print(f"Device: {device}")

    print("=== Loading Olist corrected sentiment split (same seed/procedure as the deployed checkpoint) ===")
    reviews = pd.read_csv(PROJECT_ROOT / "data" / "interim" / "reviews_translated.csv")
    sent_df = prep.build_sentiment_dataframe(reviews)
    deduped, _ = prep.remove_duplicate_reviews(sent_df)
    split = prep.split_sentiment_dataset(deduped, seed=args.seed)
    print(f"Olist train/val/test: {len(split.train)}/{len(split.val)}/{len(split.test)}")

    print("\n=== Building late/delivery augmentation from Olist TRAIN split only ===")
    train_late_mask = split.train["text"].str.contains(LATE_DELAY_PATTERN, case=False, regex=True, na=False)
    train_late_negatives = split.train[train_late_mask & (split.train["label"] == 0)]
    print(f"Real TRAIN-split negative late/delay reviews: {len(train_late_negatives)} (oversampled x{args.negative_oversample})")
    oversampled_real = pd.concat([train_late_negatives[["text", "label"]]] * args.negative_oversample, ignore_index=True)

    synthetic_df = build_synthetic_examples()
    print(f"Synthetic templates: {(synthetic_df['label'] == 0).sum()} negative, {(synthetic_df['label'] == 1).sum()} positive")

    print("\n=== Verifying the hand-crafted eval set is genuinely held out ===")
    assert_eval_is_held_out(synthetic_df, pd.concat([split.train["text"], oversampled_real["text"]], ignore_index=True), NEGATION_EVAL_SET)
    print(f"OK: none of the {len(NEGATION_EVAL_SET)} eval items appear in the training set.")

    train_texts = pd.concat([split.train["text"], oversampled_real["text"], synthetic_df["text"]], ignore_index=True)
    train_labels = pd.concat([split.train["label"], oversampled_real["label"], synthetic_df["label"]], ignore_index=True)
    print(f"Combined BERT train set: {len(train_texts)} (Olist {len(split.train)} + real-late-oversampled {len(oversampled_real)} + synthetic {len(synthetic_df)})")

    print("\n=== Loading the currently-deployed fine-tuned BERT checkpoint (continuing training, not from scratch) ===")
    bert_path = PROJECT_ROOT / "models" / "bert_review_sentiment"
    baseline_fingerprint = checkpoint_fingerprint(bert_path)
    model, tokenizer = ml_models.load_fine_tuned_bert(bert_path, device=device)
    model.to(device)

    print("\n=== Baseline: late/delay false-positive rate on the TEST split, BEFORE this run's training ===")
    test_late_mask = split.test["text"].str.contains(LATE_DELAY_PATTERN, case=False, regex=True, na=False)
    late_eval_df = split.test[test_late_mask].copy()
    fp_before, n_fp_before, n_neg_before = late_delay_fp_rate(model, late_eval_df["text"], late_eval_df["label"], tokenizer, device, args.max_len, args.batch_size)
    lo_before, hi_before = wilson_confint(n_fp_before, n_neg_before)
    print(f"Late/delay test-split subset: {len(late_eval_df)} rows, {n_neg_before} genuinely negative")
    print(f"FP rate BEFORE: {fp_before:.1%} ({n_fp_before}/{n_neg_before}), 95% CI [{lo_before:.1%}, {hi_before:.1%}]")

    train_loader = ds.build_bert_dataloader(train_texts.tolist(), train_labels.tolist(), tokenizer, args.max_len, args.batch_size, shuffle=True)
    val_loader = ds.build_bert_dataloader(split.val["text"].tolist(), split.val["label"].tolist(), tokenizer, args.max_len, args.batch_size, shuffle=False)
    test_loader = ds.build_bert_dataloader(split.test["text"].tolist(), split.test["label"].tolist(), tokenizer, args.max_len, args.batch_size, shuffle=False)

    print(f"\n=== Continued fine-tuning: {args.epochs} epoch(s), lr={args.learning_rate}, batch_size={args.batch_size} ===")
    from transformers import get_linear_schedule_with_warmup
    total_steps = len(train_loader) * args.epochs
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps)

    start_time = time.time()
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = run_bert_epoch(model, train_loader, device, optimizer, scheduler)
        val_loss, val_acc = run_bert_epoch(model, val_loader, device)
        print(f"Epoch {epoch}: train_loss={train_loss:.4f} train_acc={train_acc:.4f} val_loss={val_loss:.4f} val_acc={val_acc:.4f}")
    train_time = time.time() - start_time
    print(f"Trained in {train_time:.1f}s")

    print("\n=== Evaluating on Olist TEST set (unaugmented, unchanged) ===")
    y_true, y_pred, y_prob = ev.get_bert_predictions(model, test_loader)
    new_test_metrics = ev.evaluate_classification(y_true, y_pred, y_prob)
    print(new_test_metrics.to_dict())

    print("\n=== Late/delay false-positive rate on the SAME test-split rows, AFTER training ===")
    fp_after, n_fp_after, n_neg_after = late_delay_fp_rate(model, late_eval_df["text"], late_eval_df["label"], tokenizer, device, args.max_len, args.batch_size)
    lo_after, hi_after = wilson_confint(n_fp_after, n_neg_after)
    print(f"FP rate AFTER: {fp_after:.1%} ({n_fp_after}/{n_neg_after}), 95% CI [{lo_after:.1%}, {hi_after:.1%}]")

    print("\n=== Hand-crafted eval set (genuinely held out -- verified above) ===")
    model.eval()
    correct = 0
    eval_results = []
    with torch.no_grad():
        for text, expected in NEGATION_EVAL_SET:
            enc = tokenizer([text], max_length=args.max_len, padding=True, truncation=True, return_tensors="pt").to(device)
            logits = model(**enc).logits
            probs = torch.softmax(logits, dim=1)[0]
            pred = int(torch.argmax(probs))
            is_correct = pred == expected
            correct += is_correct
            eval_results.append({"text": text, "expected": expected, "predicted": pred, "prob_positive": round(float(probs[1]), 4), "correct": is_correct})
            print(f"  [{'OK' if is_correct else 'FAIL'}] '{text}' -> pred={pred} (expected {expected}), p_pos={float(probs[1]):.3f}")
    hand_eval_accuracy = correct / len(NEGATION_EVAL_SET)
    print(f"\nHand-crafted eval accuracy (genuinely held out): {hand_eval_accuracy:.1%} ({correct}/{len(NEGATION_EVAL_SET)})")

    # Regression guard for --apply: refuse to overwrite the shipped
    # checkpoint if f1_macro on the untouched test set got worse than a
    # small noise tolerance. Previously --apply's own --help text promised
    # this guard existed; it didn't -- see Technical Review #05.
    baseline_metrics_path = PROJECT_ROOT / "results" / "reproduced_metrics.json"
    regressed = None
    old_f1 = None
    if baseline_metrics_path.is_file():
        baseline = json.loads(baseline_metrics_path.read_text(encoding="utf-8"))
        old_f1 = baseline.get("bert", {}).get("test", {}).get("metrics", {}).get("f1_macro")
        if old_f1 is not None:
            new_f1 = new_test_metrics.to_dict()["f1_macro"]
            regressed = new_f1 < old_f1 - REGRESSION_TOLERANCE
            print(f"\nRegression check: f1_macro {old_f1:.4f} -> {new_f1:.4f} (tolerance {REGRESSION_TOLERANCE}) -> {'REGRESSED' if regressed else 'OK'}")
    else:
        print(f"\nNo baseline at {baseline_metrics_path} to compare against -- run scripts/regenerate_metrics.py first. Regression check skipped.")

    report = {
        "augmentation": {
            "real_train_negatives_found": len(train_late_negatives),
            "negative_oversample": args.negative_oversample,
            "synthetic_negative_templates": int((synthetic_df["label"] == 0).sum()),
            "synthetic_positive_templates": int((synthetic_df["label"] == 1).sum()),
            "combined_train_size": len(train_texts),
        },
        "training": {"epochs": args.epochs, "learning_rate": args.learning_rate, "batch_size": args.batch_size, "train_time_seconds": train_time},
        "baseline_checkpoint_sha256": baseline_fingerprint,
        "olist_test_metrics_new": new_test_metrics.to_dict(),
        "late_delay_eval": {
            "n_rows": len(late_eval_df),
            "n_negatives": n_neg_after,
            "fp_rate_before": {"point": fp_before, "ci95": [lo_before, hi_before], "n_fp": n_fp_before},
            "fp_rate_after": {"point": fp_after, "ci95": [lo_after, hi_after], "n_fp": n_fp_after},
            "measured_on": "split.test only (held out from training)",
        },
        "hand_crafted_eval_accuracy": hand_eval_accuracy,
        "hand_crafted_eval_held_out_verified": True,
        "hand_crafted_eval_details": eval_results,
        "regression_check": {"baseline_f1_macro": old_f1, "regressed": regressed, "tolerance": REGRESSION_TOLERANCE},
        "applied": False,
    }

    if not args.apply:
        write_json(PROJECT_ROOT / "results" / "bert_late_delivery_augmentation_report.json", report)
        print("\n(dry run -- pass --apply to overwrite the shipped checkpoint)")
        return

    if regressed and not args.force:
        write_json(PROJECT_ROOT / "results" / "bert_late_delivery_augmentation_report.json", report)
        raise SystemExit(
            f"REFUSING to apply: f1_macro regressed {old_f1:.4f} -> {new_test_metrics.to_dict()['f1_macro']:.4f} "
            f"(tolerance {REGRESSION_TOLERANCE}). Re-run with --force to override."
        )

    print("\n=== --apply: overwriting shipped BERT checkpoint ===")
    out_dir = bert_path
    backup = out_dir.parent / f"{out_dir.name}.bak.{datetime.now():%Y%m%d%H%M%S}"
    shutil.copytree(out_dir, backup)
    print(f"Backed up previous checkpoint to {backup}")

    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"Saved fine-tuned BERT to {out_dir}")

    report["applied"] = True
    report["backup_path"] = str(backup)
    write_json(PROJECT_ROOT / "results" / "bert_late_delivery_augmentation_report.json", report)

    print("\n=== Regenerating published metrics so they match the new checkpoint (see Technical Review #03) ===")
    print("Run: python scripts/regenerate_metrics.py")


if __name__ == "__main__":
    main()
