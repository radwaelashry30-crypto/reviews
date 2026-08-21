#!/usr/bin/env python
"""TF-IDF + Logistic Regression fake-review detector -- tests a specific
hypothesis about WHY the DistilBERT attempts stayed unstable under length
perturbation even after two rounds of dedicated consistency training (see
results/fake_review_detector_v2_consistency_training.json and its w1.0/w4.0
backups): a transformer processes text positionally/contextually, so an
appended clause can shift its internal representation of the whole sequence
even though the clause itself is irrelevant. A bag-of-words linear model has
no such mechanism -- appending neutral filler mostly adds near-zero-weight
features to a sparse vector and barely moves a dot product. If that
mechanistic story is right, this simpler model should be inherently more
length-robust without any special training for it.

Same dataset (Ott et al.), same leak-free split, same paraphrase-stability
protocol as scripts/paraphrase_stability_test.py, so results are directly
comparable to the three DistilBERT attempts.

Usage:
    python scripts/train_fake_review_detector_tfidf.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml.utils import set_seed, write_json  # noqa: E402
from train_fake_review_detector_v2_consistency import (  # noqa: E402
    LABEL_MAPPING, SRC_CSV, load_and_clean, split_dataset, wilson_confint,
)

# Same 6 paraphrase pairs + length-filler probe as scripts/paraphrase_stability_test.py
PARAPHRASE_PAIRS: list[tuple[str, str]] = [
    ("The material feels flimsy and the color is different from the photos.",
     "The fabric feels cheap and the color doesn't match the pictures."),
    ("This product exceeded my expectations, the build quality is excellent.",
     "This item surpassed what I expected, the construction quality is great."),
    ("Terrible experience, it broke after two days and support never replied.",
     "Awful experience, it stopped working after two days and customer service never responded."),
    ("Fast shipping and exactly as described, very happy with this purchase.",
     "Quick delivery and precisely as advertised, extremely satisfied with this order."),
    ("I would not recommend this seller, the item arrived damaged and late.",
     "I wouldn't suggest buying from this vendor, the product showed up broken and behind schedule."),
    ("Good value for the price, works as expected with no issues so far.",
     "Decent value for the cost, functions as anticipated with no problems yet."),
]
LENGTH_BASE = "The product works fine and arrived on time."
LENGTH_FILLERS = [
    "",
    " I ordered it last week.",
    " I ordered it last week, and it came in a small box.",
    " I ordered it last week, and it came in a small box with a printed receipt inside.",
]


def main() -> None:
    set_seed(42)
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

    print("=== Loading Ott et al. Deceptive Opinion Spam Corpus ===")
    df = load_and_clean()
    train_df, val_df, test_df = split_dataset(df, seed=42)
    # TF-IDF has no separate "epoch" concept -- fold val into train (more
    # signal for a linear model on an already-small 1,596-row corpus).
    fit_df = pd.concat([train_df, val_df], ignore_index=True)

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=8000, stop_words="english", sublinear_tf=True)
    X_train = vectorizer.fit_transform(fit_df["text"])
    X_test = vectorizer.transform(test_df["text"])
    y_train = fit_df["label"].to_numpy()
    y_test = test_df["label"].to_numpy()

    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced", random_state=42)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]
    n_correct = int((y_test == y_pred).sum())

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "accuracy_95ci": wilson_confint(n_correct, len(y_test)),
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "n_test": int(len(y_test)),
    }
    print("\n=== Held-out TEST metrics ===")
    print(metrics)
    cm = confusion_matrix(y_test, y_pred).tolist()
    print("Confusion matrix [[TN,FP],[FN,TP]]:", cm)
    print(classification_report(y_test, y_pred, target_names=["REAL", "FAKE"]))

    def fake_prob(text: str) -> float:
        return float(clf.predict_proba(vectorizer.transform([text]))[0, 1])

    print("\n=== Paraphrase-stability test (same 6 pairs as scripts/paraphrase_stability_test.py) ===")
    diffs, flips = [], 0
    for i, (a, b) in enumerate(PARAPHRASE_PAIRS, 1):
        pa, pb = fake_prob(a), fake_prob(b)
        diff = abs(pa - pb)
        diffs.append(diff)
        flip = (pa >= 0.5) != (pb >= 0.5)
        flips += int(flip)
        print(f"[{i}] P(fake) original={pa:.4f} paraphrase={pb:.4f} |diff|={diff:.4f} decision_flip={flip}")
    mean_diff = sum(diffs) / len(diffs)
    max_diff = max(diffs)
    print(f"\nMean |diff|: {mean_diff:.4f}  Max |diff|: {max_diff:.4f}  Flips: {flips}/{len(PARAPHRASE_PAIRS)}")

    print("\n=== Length-robustness check ===")
    length_probs = [fake_prob(LENGTH_BASE + f) for f in LENGTH_FILLERS]
    for f, p in zip(LENGTH_FILLERS, length_probs):
        print(f"len={len(LENGTH_BASE + f):3d}  P(fake)={p:.4f}  text={(LENGTH_BASE + f)!r}")
    length_spread = max(length_probs) - min(length_probs)
    print(f"Spread across filler lengths: {length_spread:.4f}")

    passed = flips == 0 and mean_diff < 0.15 and length_spread < 0.15
    print("\n=== Verdict ===")
    print("PASS" if passed else "FAIL", ": predictions", "are" if passed else "are NOT", "stable under paraphrasing and length variation.")

    out_dir = PROJECT_ROOT / "models" / "fake_review_detector_tfidf"
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(vectorizer, out_dir / "vectorizer.pkl")
    joblib.dump(clf, out_dir / "classifier.pkl")
    print(f"\nSaved -> {out_dir}")

    write_json(PROJECT_ROOT / "results" / "fake_review_detector_tfidf_training.json", {
        "approach": "TF-IDF (1-2 grams, 8000 features) + Logistic Regression (class_weight=balanced)",
        "dataset": "Ott et al. Deceptive Opinion Spam Corpus (Cornell, ACL 2011 / NAACL 2013)",
        "dataset_size": len(df),
        "split_sizes": {"train_plus_val": len(fit_df), "test": len(test_df)},
        "test_metrics": metrics,
        "confusion_matrix": cm,
        "stability_test": {
            "mean_diff": mean_diff, "max_diff": max_diff, "flips": flips, "n_pairs": len(PARAPHRASE_PAIRS),
            "length_spread": length_spread, "passed": bool(passed),
        },
        "sklearn_version_used": __import__("sklearn").__version__,
        "domain_shift_caveat": "Trained on hotel reviews (Chicago hotels); applied in this app to Olist e-commerce reviews. Not the same domain.",
        "seed": 42,
    })


if __name__ == "__main__":
    main()
