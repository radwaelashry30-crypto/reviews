#!/usr/bin/env python
"""Re-evaluates every fake-review checkpoint trained in this project under a
3-way decision rule (REAL / UNCERTAIN / FAKE) instead of a hard 0.5 cutoff.

Why: every stability failure observed so far (TF-IDF: 2/6 flips, ensemble:
2/6 flips) happened at probabilities close to 0.5 (e.g. 0.48 -> 0.52) -- the
model's two views of the "same" review both land in genuinely ambiguous
territory, and a hard threshold turns a small, honest uncertainty into a
loud, confident-looking "decision flip". An UNCERTAIN band around 0.5 doesn't
change what the model believes; it changes what it's allowed to CLAIM. A
"flip" only counts here if the model was confident on BOTH sides and those
confident verdicts disagree -- which is a materially different (and
arguably more honest) claim than the current single-shot API response makes.

Usage:
    python scripts/fake_review_abstain_zone_test.py --margin 0.1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from train_fake_review_detector_tfidf import PARAPHRASE_PAIRS, LENGTH_BASE, LENGTH_FILLERS  # noqa: E402

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


def evaluate(name: str, prob_fn, margin: float) -> None:
    print(f"\n{'=' * 60}\n{name}  (margin={margin})\n{'=' * 60}")

    print("--- Paraphrase pairs ---")
    confident_flips = 0
    n_abstained = 0
    diffs = []
    for i, (a, b) in enumerate(PARAPHRASE_PAIRS, 1):
        pa, pb = prob_fn(a), prob_fn(b)
        da, db = decide(pa, margin), decide(pb, margin)
        diffs.append(abs(pa - pb))
        flip = da != "UNCERTAIN" and db != "UNCERTAIN" and da != db
        abstained = da == "UNCERTAIN" or db == "UNCERTAIN"
        confident_flips += int(flip)
        n_abstained += int(abstained)
        print(f"[{i}] p={pa:.3f}->{da:<10} p={pb:.3f}->{db:<10} confident_flip={flip}")
    print(f"Confident decision flips: {confident_flips}/{len(PARAPHRASE_PAIRS)}  "
          f"(pairs where at least one side abstained: {n_abstained}/{len(PARAPHRASE_PAIRS)})")

    print("--- Length filler ---")
    decisions = []
    for f in LENGTH_FILLERS:
        p = prob_fn(LENGTH_BASE + f)
        d = decide(p, margin)
        decisions.append(d)
        print(f"p={p:.3f} -> {d:<10} text={(LENGTH_BASE + f)!r}")
    confident_decisions = {d for d in decisions if d != "UNCERTAIN"}
    length_stable = len(confident_decisions) <= 1
    print(f"Confident decisions across length variants: {confident_decisions or '{}'}  "
          f"-> {'stable' if length_stable else 'DISAGREE'}")

    passed = confident_flips == 0 and length_stable
    print(f"\nVerdict: {'PASS' if passed else 'FAIL'} under margin={margin} abstain-zone rule.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--margin", type=float, default=0.1, help="Half-width of the UNCERTAIN band around 0.5")
    args = parser.parse_args()

    print("Loading checkpoints...")
    bert_prob = load_bert_prob()
    tfidf_prob = load_tfidf_prob()

    def ensemble_prob(text: str) -> float:
        return (bert_prob(text) + tfidf_prob(text)) / 2.0

    evaluate("DistilBERT + consistency (v3)", bert_prob, args.margin)
    evaluate("TF-IDF + Logistic Regression", tfidf_prob, args.margin)
    evaluate("Ensemble (mean)", ensemble_prob, args.margin)


if __name__ == "__main__":
    main()
