#!/usr/bin/env python
"""Statistically meaningful version of the stability check: instead of 6
hand-picked paraphrase pairs, generates a WordNet paraphrase for EVERY
review in the held-out test split (n=320) and measures the real flip rate
with a Wilson confidence interval -- plus the abstain rate under the
uncertain-zone decision rule, so a "PASS" can't come from just refusing to
answer most of the time without that being visible.

Usage:
    python scripts/fake_review_stability_largescale_test.py --margin 0.1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml.utils import write_json  # noqa: E402
from train_fake_review_detector_v2_consistency import split_dataset, load_and_clean, wordnet_paraphrase, wilson_confint  # noqa: E402

BERT_DIR = PROJECT_ROOT / "models" / "fake_review_detector_v2_consistency"
TFIDF_DIR = PROJECT_ROOT / "models" / "fake_review_detector_tfidf"


def load_bert_prob():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(BERT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(BERT_DIR)
    model.eval()

    @torch.no_grad()
    def bert_prob(text: str) -> float:
        enc = tokenizer(text, truncation=True, max_length=256, return_tensors="pt")
        enc = {k: v for k, v in enc.items() if k in ("input_ids", "attention_mask")}
        logits = model(**enc).logits
        return float(torch.softmax(logits, dim=1)[0, 1].item())

    return bert_prob


def load_tfidf_prob():
    vectorizer = joblib.load(TFIDF_DIR / "vectorizer.pkl")
    clf = joblib.load(TFIDF_DIR / "classifier.pkl")

    def tfidf_prob(text: str) -> float:
        return float(clf.predict_proba(vectorizer.transform([text]))[0, 1])

    return tfidf_prob


def decide(p: float, margin: float) -> str:
    if p >= 0.5 + margin:
        return "FAKE"
    if p <= 0.5 - margin:
        return "REAL"
    return "UNCERTAIN"


def evaluate(name: str, prob_fn, pairs: list[tuple[str, str]], margin: float) -> dict:
    n = len(pairs)
    raw_flips = 0
    confident_flips = 0
    n_at_least_one_uncertain = 0
    n_both_confident = 0
    diffs = []
    for a, b in pairs:
        pa, pb = prob_fn(a), prob_fn(b)
        diffs.append(abs(pa - pb))
        raw_flips += int((pa >= 0.5) != (pb >= 0.5))
        da, db = decide(pa, margin), decide(pb, margin)
        if da == "UNCERTAIN" or db == "UNCERTAIN":
            n_at_least_one_uncertain += 1
        else:
            n_both_confident += 1
            confident_flips += int(da != db)

    raw_flip_rate = raw_flips / n
    raw_ci = wilson_confint(raw_flips, n)
    confident_flip_rate = (confident_flips / n_both_confident) if n_both_confident else 0.0
    confident_ci = wilson_confint(confident_flips, n_both_confident) if n_both_confident else (0.0, 0.0)
    abstain_rate = n_at_least_one_uncertain / n

    print(f"\n{'=' * 70}\n{name}  (n={n} held-out test reviews, margin={margin})\n{'=' * 70}")
    print(f"Mean |P(fake) diff| across all pairs: {sum(diffs)/n:.4f}  (max: {max(diffs):.4f})")
    print(f"RAW flip rate (hard 0.5 threshold, no abstain): {raw_flips}/{n} = {raw_flip_rate:.1%}  "
          f"(95% CI: {raw_ci[0]:.1%}-{raw_ci[1]:.1%})")
    print(f"Abstain rate (>=1 side landed in UNCERTAIN band): {n_at_least_one_uncertain}/{n} = {abstain_rate:.1%}")
    print(f"CONFIDENT flip rate (both sides confident, then disagree): {confident_flips}/{n_both_confident} = "
          f"{confident_flip_rate:.1%}  (95% CI: {confident_ci[0]:.1%}-{confident_ci[1]:.1%})")

    return {
        "n_pairs": n, "mean_diff": sum(diffs) / n, "max_diff": max(diffs),
        "raw_flip_rate": raw_flip_rate, "raw_flip_95ci": raw_ci,
        "abstain_rate": abstain_rate,
        "confident_flip_count": confident_flips, "n_both_confident": n_both_confident,
        "confident_flip_rate": confident_flip_rate, "confident_flip_95ci": confident_ci,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--margin", type=float, default=0.1)
    args = parser.parse_args()

    print("Loading checkpoints...")
    bert_prob = load_bert_prob()
    tfidf_prob = load_tfidf_prob()

    def ensemble_prob(text: str) -> float:
        return (bert_prob(text) + tfidf_prob(text)) / 2.0

    print("Loading held-out TEST split and generating a WordNet paraphrase for EVERY review in it...")
    df = load_and_clean()
    _, _, test_df = split_dataset(df, seed=42)

    pairs = []
    n_no_paraphrase = 0
    for text in test_df["text"]:
        p = wordnet_paraphrase(text, max_swaps=4)
        if p is None or p == text:
            n_no_paraphrase += 1
            continue
        pairs.append((text, p))
    print(f"Built {len(pairs)} genuine (original, paraphrase) pairs from the test split "
          f"({n_no_paraphrase} test reviews had no substitutable words, skipped)")

    results = {}
    results["distilbert_consistency_v4"] = evaluate("DistilBERT + consistency (round 4)", bert_prob, pairs, args.margin)
    results["tfidf_logreg"] = evaluate("TF-IDF + Logistic Regression", tfidf_prob, pairs, args.margin)
    results["ensemble"] = evaluate("Ensemble (mean)", ensemble_prob, pairs, args.margin)

    write_json(PROJECT_ROOT / "results" / "fake_review_stability_largescale_test.json", {
        "n_test_reviews": len(test_df), "n_pairs_evaluated": len(pairs), "margin": args.margin, "models": results,
    })


if __name__ == "__main__":
    main()
