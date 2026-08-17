"""Threshold and calibration analysis for BERT and CNN2D.

Neither the deployed 0.5 decision threshold nor the reliability of each
model's reported probabilities had ever been empirically checked -- 0.5 was
simply the conventional default. This script:

  1. Sweeps candidate thresholds (0.30-0.70) on the VALIDATION split only
     (never test) and reports accuracy/precision/recall/F1 at each, to check
     whether 0.5 is actually a reasonable choice or whether a different
     threshold would trade errors more favorably.
  2. Computes calibration metrics on the same validation split: Brier score
     (lower is better, 0=perfect) and Expected Calibration Error (ECE, 10
     equal-width bins) -- i.e. when the model says "90% confident", is it
     actually right about 90% of the time?

Uses the exact same TRAIN/VAL/TEST split (seed=42, dedupe-before-split) as
the deployed checkpoints, so validation rows here were never trained on and
were never touched by the reported test-set metrics either.

Usage:
    python scripts/calibration_analysis.py --model bert
    python scripts/calibration_analysis.py --model cnn2d
    python scripts/calibration_analysis.py --model both
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml import datasets as ds, evaluation as ev, models as ml_models, preprocessing as prep  # noqa: E402
from app.ml.utils import get_device, set_seed, write_json  # noqa: E402

THRESHOLDS = [round(t, 2) for t in np.arange(0.30, 0.71, 0.05)]
N_ECE_BINS = 10


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_prob - y_true) ** 2))


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = N_ECE_BINS) -> dict:
    """Standard ECE: bins predictions by confidence in the predicted class,
    compares each bin's average confidence to its actual accuracy, weights by
    bin size. Also returns the per-bin table for transparency."""
    y_pred = (y_prob >= 0.5).astype(int)
    confidence = np.where(y_pred == 1, y_prob, 1 - y_prob)
    correct = (y_pred == y_true).astype(float)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    bins = []
    n = len(y_true)
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (confidence > lo) & (confidence <= hi) if i > 0 else (confidence >= lo) & (confidence <= hi)
        bin_n = int(mask.sum())
        if bin_n == 0:
            bins.append({"range": [round(lo, 2), round(hi, 2)], "n": 0, "avg_confidence": None, "accuracy": None})
            continue
        avg_conf = float(confidence[mask].mean())
        acc = float(correct[mask].mean())
        ece += (bin_n / n) * abs(avg_conf - acc)
        bins.append({"range": [round(lo, 2), round(hi, 2)], "n": bin_n, "avg_confidence": round(avg_conf, 4), "accuracy": round(acc, 4)})

    return {"ece": round(ece, 4), "bins": bins}


def threshold_sweep(y_true: np.ndarray, y_prob: np.ndarray) -> list[dict]:
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

    rows = []
    for t in THRESHOLDS:
        y_pred = (y_prob >= t).astype(int)
        rows.append({
            "threshold": t,
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        })
    return rows


def analyze_bert(split, device) -> dict:
    print("\n=== BERT: loading fine-tuned checkpoint ===")
    model, tokenizer = ml_models.load_fine_tuned_bert(PROJECT_ROOT / "models" / "bert_review_sentiment", device=device)
    model.to(device)
    val_loader = ds.build_bert_dataloader(split.val["text"].tolist(), split.val["label"].tolist(), tokenizer, max_len=128, batch_size=32, shuffle=False)
    y_true, y_pred_default, y_prob = ev.get_bert_predictions(model, val_loader)
    return {"y_true": y_true, "y_prob": y_prob}


def analyze_cnn2d(split, device) -> dict:
    print("\n=== CNN2D: loading checkpoint + tokenizer ===")
    with open(PROJECT_ROOT / "artifacts" / "cnn2d_tokenizer.pkl", "rb") as f:
        tokenizer = pickle.load(f)
    model = ml_models.load_cnn2d_model(PROJECT_ROOT / "models" / "cnn2d_review_sentiment.pt", device=device)
    X_val_seq = ds.encode_texts_for_cnn(split.val["text"], tokenizer, max_len=100)
    val_loader = ds.build_cnn_dataloader(X_val_seq, split.val["label"], batch_size=64, shuffle=False)
    y_true, y_pred_default, y_prob = ev.get_cnn_predictions(model, val_loader)
    return {"y_true": y_true, "y_prob": y_prob}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["bert", "cnn2d", "both"], default="both")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    device = get_device()
    print(f"Device: {device}")

    print("=== Loading Olist corrected sentiment split (same seed/procedure as deployed checkpoints) ===")
    reviews = pd.read_csv(PROJECT_ROOT / "data" / "interim" / "reviews_translated.csv")
    sent_df = prep.build_sentiment_dataframe(reviews)
    deduped, _ = prep.remove_duplicate_reviews(sent_df)
    split = prep.split_sentiment_dataset(deduped, seed=args.seed)
    print(f"Olist train/val/test: {len(split.train)}/{len(split.val)}/{len(split.test)} (VALIDATION used below, never test)")

    models_to_run = ["bert", "cnn2d"] if args.model == "both" else [args.model]
    report: dict = {"validation_size": len(split.val), "seed": args.seed}

    for model_name in models_to_run:
        result = analyze_bert(split, device) if model_name == "bert" else analyze_cnn2d(split, device)
        y_true, y_prob = result["y_true"], result["y_prob"]

        sweep = threshold_sweep(y_true, y_prob)
        best_f1 = max(sweep, key=lambda r: r["f1"])
        default_row = next(r for r in sweep if r["threshold"] == 0.5)

        print(f"\n--- {model_name.upper()} threshold sweep (validation, n={len(y_true)}) ---")
        for row in sweep:
            marker = " <- default" if row["threshold"] == 0.5 else (" <- best F1" if row["threshold"] == best_f1["threshold"] else "")
            print(f"  t={row['threshold']:.2f}  acc={row['accuracy']:.4f}  prec={row['precision']:.4f}  rec={row['recall']:.4f}  f1={row['f1']:.4f}{marker}")

        brier = brier_score(y_true, y_prob)
        ece_result = expected_calibration_error(y_true, y_prob)
        print(f"\n  Brier score: {brier:.4f} (0=perfect, 0.25=uninformative-coin-flip baseline)")
        print(f"  ECE: {ece_result['ece']:.4f} (0=perfectly calibrated)")

        report[model_name] = {
            "threshold_sweep": sweep,
            "default_threshold_0.5": default_row,
            "best_f1_threshold": best_f1,
            "brier_score": round(brier, 4),
            "ece": ece_result,
        }

    out_path = PROJECT_ROOT / "results" / "calibration_analysis.json"
    write_json(out_path, report)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
