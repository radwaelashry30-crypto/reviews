#!/usr/bin/env python
"""Ensembles the two fake-review detectors trained in this project (see
train_fake_review_detector_v2_consistency.py and train_fake_review_detector_tfidf.py),
each of which independently fixed a DIFFERENT half of the paraphrase-stability
test: DistilBERT+consistency-training fixed synonym-substitution instability
(0/6 flips) but not length-sensitivity (spread 0.24, needs <0.15); TF-IDF+LR
fixed length-sensitivity (spread 0.138) but has small boundary-adjacent
synonym flips (2/6, but max diff only 0.085 -- nothing like the original
checkpoint's 99.9%->0.1% swings). Averaging their fake-probabilities tests
whether the two failure modes cancel out.

Usage:
    python scripts/fake_review_ensemble_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml.utils import write_json  # noqa: E402
from train_fake_review_detector_v2_consistency import split_dataset, load_and_clean, wilson_confint  # noqa: E402
from train_fake_review_detector_tfidf import PARAPHRASE_PAIRS, LENGTH_BASE, LENGTH_FILLERS  # noqa: E402

BERT_DIR = PROJECT_ROOT / "models" / "fake_review_detector_v2_consistency"
TFIDF_DIR = PROJECT_ROOT / "models" / "fake_review_detector_tfidf"


def load_bert():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(BERT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(BERT_DIR)
    model.eval()
    device = torch.device("cpu")
    model.to(device)

    @torch.no_grad()
    def bert_prob(text: str) -> float:
        enc = tokenizer(text, truncation=True, max_length=256, return_tensors="pt").to(device)
        enc = {k: v for k, v in enc.items() if k in ("input_ids", "attention_mask")}
        logits = model(**enc).logits
        return float(torch.softmax(logits, dim=1)[0, 1].item())

    return bert_prob


def load_tfidf():
    vectorizer = joblib.load(TFIDF_DIR / "vectorizer.pkl")
    clf = joblib.load(TFIDF_DIR / "classifier.pkl")

    def tfidf_prob(text: str) -> float:
        return float(clf.predict_proba(vectorizer.transform([text]))[0, 1])

    return tfidf_prob


def main() -> None:
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

    print("Loading both checkpoints...")
    bert_prob = load_bert()
    tfidf_prob = load_tfidf()

    def ensemble_prob(text: str) -> float:
        return (bert_prob(text) + tfidf_prob(text)) / 2.0

    print("=== Loading held-out TEST split (same seed=42 split as both individual models) ===")
    df = load_and_clean()
    _, _, test_df = split_dataset(df, seed=42)

    y_true = test_df["label"].to_numpy()
    y_prob = np.array([ensemble_prob(t) for t in test_df["text"]])
    y_pred = (y_prob >= 0.5).astype(int)
    n_correct = int((y_true == y_pred).sum())

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "accuracy_95ci": wilson_confint(n_correct, len(y_true)),
        "precision": float(precision_score(y_true, y_pred)),
        "recall": float(recall_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "n_test": int(len(y_true)),
    }
    print("\n=== Ensemble held-out TEST metrics ===")
    print(metrics)
    cm = confusion_matrix(y_true, y_pred).tolist()
    print("Confusion matrix [[TN,FP],[FN,TP]]:", cm)
    print(classification_report(y_true, y_pred, target_names=["REAL", "FAKE"]))

    print("\n=== Paraphrase-stability test (ensemble) ===")
    diffs, flips = [], 0
    for i, (a, b) in enumerate(PARAPHRASE_PAIRS, 1):
        pa, pb = ensemble_prob(a), ensemble_prob(b)
        diff = abs(pa - pb)
        diffs.append(diff)
        flip = (pa >= 0.5) != (pb >= 0.5)
        flips += int(flip)
        print(f"[{i}] P(fake) original={pa:.4f} paraphrase={pb:.4f} |diff|={diff:.4f} decision_flip={flip}")
    mean_diff = sum(diffs) / len(diffs)
    max_diff = max(diffs)
    print(f"\nMean |diff|: {mean_diff:.4f}  Max |diff|: {max_diff:.4f}  Flips: {flips}/{len(PARAPHRASE_PAIRS)}")

    print("\n=== Length-robustness check (ensemble) ===")
    length_probs = [ensemble_prob(LENGTH_BASE + f) for f in LENGTH_FILLERS]
    for f, p in zip(LENGTH_FILLERS, length_probs):
        print(f"len={len(LENGTH_BASE + f):3d}  P(fake)={p:.4f}  text={(LENGTH_BASE + f)!r}")
    length_spread = max(length_probs) - min(length_probs)
    print(f"Spread across filler lengths: {length_spread:.4f}")

    passed = flips == 0 and mean_diff < 0.15 and length_spread < 0.15
    print("\n=== Verdict ===")
    print("PASS" if passed else "FAIL", ": predictions", "are" if passed else "are NOT", "stable under paraphrasing and length variation.")

    write_json(PROJECT_ROOT / "results" / "fake_review_detector_ensemble_test.json", {
        "approach": "Mean of DistilBERT+consistency-training probability and TF-IDF+LogisticRegression probability",
        "components": [str(BERT_DIR.relative_to(PROJECT_ROOT)), str(TFIDF_DIR.relative_to(PROJECT_ROOT))],
        "test_metrics": metrics,
        "confusion_matrix": cm,
        "stability_test": {
            "mean_diff": mean_diff, "max_diff": max_diff, "flips": flips, "n_pairs": len(PARAPHRASE_PAIRS),
            "length_spread": length_spread, "passed": bool(passed),
        },
    })


if __name__ == "__main__":
    main()
