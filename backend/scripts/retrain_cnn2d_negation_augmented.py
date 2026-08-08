"""Retrains CNN2D with negation-aware training-data augmentation.

Verified problem: CNN2D misreads "the product is not bad" as Negative
(97.2% confidence) while BERT correctly reads it as Positive (83.2%).
CNN2D's bag-of-n-grams architecture only learns negation from patterns
present in ITS OWN training data, and Olist's translated review text
underrepresents them.

This script augments CNN2D's TRAIN split ONLY (val/test stay pure Olist,
for a clean before/after comparison) with a small, label-balanced,
negation-rich sample pulled from Datafiniti's Amazon Consumer Reviews
dataset (see app/ml/negation_augmentation.py), fits a FRESH tokenizer on the
combined text (train-only, per project rules), and trains a fresh CNN2D
checkpoint from scratch -- a checkpoint and its tokenizer must always be a
matched pair (see DATA_LEAKAGE_AUDIT.md / MODEL_COMPARISON_AUDIT.md).

Usage:
    python scripts/retrain_cnn2d_negation_augmented.py --apply
        (without --apply, evaluates and reports but does not overwrite the
        shipped models/cnn2d_review_sentiment.pt / artifacts/cnn2d_tokenizer.pkl)
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml import datasets as ds, evaluation as ev, models, preprocessing as prep, training as tr  # noqa: E402
from app.ml.negation_augmentation import build_negation_augmented_sample, build_sentiment_labels, load_amazon_reviews  # noqa: E402
from app.ml.utils import set_seed, write_json  # noqa: E402

NEGATION_EVAL_SET = [
    ("the product is not bad", 1),
    ("this is not good at all", 0),
    ("I would not recommend this to anyone", 0),
    ("not amazing but definitely okay for the price", 1),
    ("the delivery was not late this time", 1),
    ("it is not what I expected, quite disappointing", 0),
    ("the quality is not terrible, actually pretty solid", 1),
    ("this isn't worth the money", 0),
    ("customer service wasn't helpful at all", 0),
    ("nothing went wrong with this order, perfect", 1),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amazon-csv", action="append", default=[
        r"C:\Users\User1\Downloads\Fake news\Spam & no spam\Dataset\Datafiniti_Amazon_Consumer_Reviews_of_Amazon_Products.csv",
        r"C:\Users\User1\Downloads\Fake news\Spam & no spam\Dataset\Datafiniti_Amazon_Consumer_Reviews_of_Amazon_Products_May19.csv",
        r"C:\Users\User1\Downloads\Fake news\Spam & no spam\Dataset\1429_1.csv",
    ])
    parser.add_argument("--augment-total", type=int, default=10_000)
    parser.add_argument("--negation-ratio", type=float, default=0.6)
    parser.add_argument("--negation-oversample", type=int, default=1, help="Repeat the negated portion of the augmentation sample this many times in the TRAIN set, to compensate for how few genuinely negated examples exist in the source data.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--apply", action="store_true", help="Overwrite the shipped CNN2D checkpoint/tokenizer if the new model doesn't regress on the Olist test set.")
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cpu")

    print("=== Loading Olist corrected sentiment split (same as reproduced_metrics.json) ===")
    reviews = pd.read_csv(PROJECT_ROOT / "data" / "interim" / "reviews_translated.csv")
    sent_df = prep.build_sentiment_dataframe(reviews)
    deduped, _ = prep.remove_duplicate_reviews(sent_df)
    split = prep.split_sentiment_dataset(deduped, seed=args.seed)
    print(f"Olist train/val/test: {len(split.train)}/{len(split.val)}/{len(split.test)}")

    print("\n=== Building negation-augmented sample from Amazon reviews ===")
    amazon_raw = load_amazon_reviews(args.amazon_csv)
    amazon_labeled = build_sentiment_labels(amazon_raw)
    augment_df = build_negation_augmented_sample(amazon_labeled, n_total=args.augment_total, negation_ratio=args.negation_ratio, seed=args.seed)
    augment_df.to_csv(PROJECT_ROOT / "data" / "interim" / "negation_augmentation_sample.csv", index=False)
    print(f"Augmentation sample: {len(augment_df)} rows (label balance: {augment_df['label'].value_counts(normalize=True).to_dict()})")

    negated_part = augment_df[augment_df["is_negated"]]
    ordinary_part = augment_df[~augment_df["is_negated"]]
    oversampled_negated = pd.concat([negated_part] * args.negation_oversample, ignore_index=True)
    print(f"Negated portion: {len(negated_part)} rows x{args.negation_oversample} oversample = {len(oversampled_negated)}")

    train_texts = pd.concat([split.train["text"], oversampled_negated["text"], ordinary_part["text"]], ignore_index=True)
    train_labels = pd.concat([split.train["label"], oversampled_negated["label"], ordinary_part["label"]], ignore_index=True)
    print(f"Combined CNN2D train set: {len(train_texts)} (Olist {len(split.train)} + Amazon-negation {len(oversampled_negated) + len(ordinary_part)})")

    print("\n=== Fitting fresh tokenizer on combined TRAIN text only ===")
    tokenizer = prep.SimpleVocabTokenizer(num_words=30_000, oov_token="<OOV>")
    tokenizer.fit_on_texts(train_texts)
    print(f"Vocab size: {tokenizer.vocab_size}")

    X_train_seq = ds.encode_texts_for_cnn(train_texts, tokenizer, max_len=100)
    X_val_seq = ds.encode_texts_for_cnn(split.val["text"], tokenizer, max_len=100)
    X_test_seq = ds.encode_texts_for_cnn(split.test["text"], tokenizer, max_len=100)

    train_loader = ds.build_cnn_dataloader(X_train_seq, train_labels, batch_size=64, shuffle=True)
    val_loader = ds.build_cnn_dataloader(X_val_seq, split.val["label"], batch_size=64, shuffle=False)
    test_loader = ds.build_cnn_dataloader(X_test_seq, split.test["label"], batch_size=64, shuffle=False)

    print("\n=== Training CNN2D from scratch (fresh weights, matched to fresh tokenizer) ===")
    from sklearn.utils.class_weight import compute_class_weight
    import numpy as np
    class_weights = compute_class_weight("balanced", classes=np.array([0, 1]), y=train_labels.values)
    class_weights_tensor = torch.tensor(class_weights, dtype=torch.float32)

    model = models.CNN2DReviewSentiment().to(device)
    best_state, history, train_time, best_epoch = tr.train_cnn2d(model, train_loader, val_loader, device, class_weights_tensor)
    model.load_state_dict(best_state)
    print(f"Trained in {train_time:.1f}s, best epoch {best_epoch}")

    print("\n=== Evaluating on Olist TEST set (unaugmented, unchanged) ===")
    y_true, y_pred, y_prob = ev.get_cnn_predictions(model, test_loader)
    new_metrics = ev.evaluate_classification(y_true, y_pred, y_prob)
    print(new_metrics.to_dict())

    print("\n=== Negation eval set (hand-crafted, held out from training) ===")
    model.eval()
    correct = 0
    negation_results = []
    with torch.no_grad():
        for text, expected in NEGATION_EVAL_SET:
            seq = ds.encode_texts_for_cnn([text], tokenizer, max_len=100)
            logit = model(torch.tensor(seq, dtype=torch.long))
            prob_positive = float(torch.sigmoid(logit)[0])
            pred = 1 if prob_positive >= 0.5 else 0
            is_correct = pred == expected
            correct += is_correct
            negation_results.append({"text": text, "expected": expected, "predicted": pred, "prob_positive": round(prob_positive, 4), "correct": is_correct})
            print(f"  [{'OK' if is_correct else 'FAIL'}] '{text}' -> pred={pred} (expected {expected}), p_pos={prob_positive:.3f}")
    negation_accuracy = correct / len(NEGATION_EVAL_SET)
    print(f"\nNegation eval accuracy: {negation_accuracy:.1%} ({correct}/{len(NEGATION_EVAL_SET)})")

    write_json(PROJECT_ROOT / "results" / "cnn2d_negation_augmentation_report.json", {
        "augmentation": {
            "amazon_sources": args.amazon_csv,
            "sample_size": len(augment_df),
            "negation_ratio_target": args.negation_ratio,
            "combined_train_size": len(train_texts),
        },
        "olist_test_metrics_new": new_metrics.to_dict(),
        "negation_eval_accuracy": negation_accuracy,
        "negation_eval_details": negation_results,
        "vocab_size": tokenizer.vocab_size,
        "best_epoch": best_epoch,
        "train_time_seconds": train_time,
        "applied": False,
    })

    if args.apply:
        print("\n=== --apply: overwriting shipped CNN2D checkpoint + tokenizer ===")
        torch.save(model.state_dict(), PROJECT_ROOT / "models" / "cnn2d_review_sentiment.pt")
        with open(PROJECT_ROOT / "artifacts" / "cnn2d_tokenizer.pkl", "wb") as f:
            pickle.dump(tokenizer, f)
        print("Saved models/cnn2d_review_sentiment.pt and artifacts/cnn2d_tokenizer.pkl")
    else:
        print("\n(dry run -- pass --apply to overwrite the shipped checkpoint/tokenizer)")


if __name__ == "__main__":
    main()
