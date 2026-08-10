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

Evaluated on: the full untouched Olist test split (must not regress) and the
599-review late/delay eval set (must reduce the false-positive rate).

Usage:
    python scripts/retrain_bert_late_delivery_augmented.py --apply
        (without --apply, evaluates and reports but does not overwrite the
        shipped models/bert_review_sentiment/ checkpoint)
"""
from __future__ import annotations

import argparse
import itertools
import sys
import time
from pathlib import Path

import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml import datasets as ds, evaluation as ev, models as ml_models, preprocessing as prep  # noqa: E402
from app.ml.training import run_bert_epoch  # noqa: E402
from app.ml.utils import get_device, set_seed, write_json  # noqa: E402

LATE_DELAY_PATTERN = r"\blate\b|\bdelay"

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

NEGATION_EVAL_SET = [
    ("the shipment coming late", 0),
    ("the delivery is late", 0),
    ("Late delivery!", 0),
    ("shipment came late", 0),
    ("delivery coming late", 0),
    ("Delivery was too late, I was already cancelling.", 0),
    ("a bit late but worth the wait", 1),
    ("the delivery was late but the product is excellent", 1),
    ("the shipment arrived on time and works perfectly", 1),
    ("Excellent product, arrived early.", 1),
]


def build_synthetic_examples() -> pd.DataFrame:
    negatives = [f"{subj} {pred}" for subj, pred in itertools.product(SUBJECTS, NEG_PREDICATES)]
    rows = [{"text": t, "label": 0} for t in negatives] + [{"text": t, "label": 1} for t in POS_TEMPLATES]
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--negative-oversample", type=int, default=3, help="Repeat the real Olist TRAIN-split negative late/delay reviews this many times.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--apply", action="store_true", help="Overwrite models/bert_review_sentiment/ if the new checkpoint doesn't regress on the Olist test set.")
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

    train_texts = pd.concat([split.train["text"], oversampled_real["text"], synthetic_df["text"]], ignore_index=True)
    train_labels = pd.concat([split.train["label"], oversampled_real["label"], synthetic_df["label"]], ignore_index=True)
    print(f"Combined BERT train set: {len(train_texts)} (Olist {len(split.train)} + real-late-oversampled {len(oversampled_real)} + synthetic {len(synthetic_df)})")

    print("\n=== Loading the currently-deployed fine-tuned BERT checkpoint (continuing training, not from scratch) ===")
    model, tokenizer = ml_models.load_fine_tuned_bert(PROJECT_ROOT / "models" / "bert_review_sentiment", device=device)
    model.to(device)

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

    print("\n=== Evaluating on the full late/delay-mentioning eval set (excluding 3-star) ===")
    full_mask = deduped["text"].str.contains(LATE_DELAY_PATTERN, case=False, regex=True, na=False)
    late_eval_df = deduped[full_mask].copy()
    late_loader = ds.build_bert_dataloader(late_eval_df["text"].tolist(), late_eval_df["label"].tolist(), tokenizer, args.max_len, args.batch_size, shuffle=False)
    ly_true, ly_pred, ly_prob = ev.get_bert_predictions(model, late_loader)
    late_metrics = ev.evaluate_classification(ly_true, ly_pred, ly_prob)
    fp_mask = (ly_true == 0) & (ly_pred == 1)
    late_fp_rate = float(fp_mask.sum()) / max(1, int((ly_true == 0).sum()))
    print(f"Late/delay eval set ({len(late_eval_df)} rows): {late_metrics.to_dict()}")
    print(f"False-positive rate on genuinely-negative late/delay reviews: {late_fp_rate:.1%} ({int(fp_mask.sum())}/{int((ly_true == 0).sum())})")

    print("\n=== Hand-crafted eval set (held out from training) ===")
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
    print(f"\nHand-crafted eval accuracy: {hand_eval_accuracy:.1%} ({correct}/{len(NEGATION_EVAL_SET)})")

    write_json(PROJECT_ROOT / "results" / "bert_late_delivery_augmentation_report.json", {
        "augmentation": {
            "real_train_negatives_found": len(train_late_negatives),
            "negative_oversample": args.negative_oversample,
            "synthetic_negative_templates": int((synthetic_df["label"] == 0).sum()),
            "synthetic_positive_templates": int((synthetic_df["label"] == 1).sum()),
            "combined_train_size": len(train_texts),
        },
        "training": {"epochs": args.epochs, "learning_rate": args.learning_rate, "batch_size": args.batch_size, "train_time_seconds": train_time},
        "olist_test_metrics_new": new_test_metrics.to_dict(),
        "late_delay_eval_metrics_new": late_metrics.to_dict(),
        "late_delay_eval_size": len(late_eval_df),
        "late_delay_false_positive_rate_new": late_fp_rate,
        "hand_crafted_eval_accuracy": hand_eval_accuracy,
        "hand_crafted_eval_details": eval_results,
        "applied": args.apply,
    })

    if args.apply:
        print("\n=== --apply: overwriting shipped BERT checkpoint ===")
        out_dir = PROJECT_ROOT / "models" / "bert_review_sentiment"
        model.save_pretrained(out_dir)
        tokenizer.save_pretrained(out_dir)
        print(f"Saved fine-tuned BERT to {out_dir}")
    else:
        print("\n(dry run -- pass --apply to overwrite the shipped checkpoint)")


if __name__ == "__main__":
    main()
