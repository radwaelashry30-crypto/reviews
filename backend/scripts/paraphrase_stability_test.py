#!/usr/bin/env python
"""Paraphrase-stability diagnostic for the fake-review detector.

This is the SAME test that exposed the original `jb10231/fake-review-
detector` checkpoint as unreliable (a pure synonym substitution flipped its
verdict from 99.9% to 0.1% confidence -- see MODEL_COMPARISON_AUDIT.md and
app/ml/fake_review_detection.py's module docstring). A good held-out test-set
score does not prove a model is robust to meaning-preserving rewording, so
this must be run -- and must pass -- before any newly trained checkpoint is
allowed to replace the disclaimed one in production.

Usage:
    python scripts/paraphrase_stability_test.py --model-dir ../models/fake_review_detector
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch

# Meaning-preserving synonym-substitution pairs. Each pair says the SAME
# thing -- a robust model should score both members of a pair similarly.
PARAPHRASE_PAIRS: list[tuple[str, str]] = [
    (
        "The material feels flimsy and the color is different from the photos.",
        "The fabric feels cheap and the color doesn't match the pictures.",
    ),
    (
        "This product exceeded my expectations, the build quality is excellent.",
        "This item surpassed what I expected, the construction quality is great.",
    ),
    (
        "Terrible experience, it broke after two days and support never replied.",
        "Awful experience, it stopped working after two days and customer service never responded.",
    ),
    (
        "Fast shipping and exactly as described, very happy with this purchase.",
        "Quick delivery and precisely as advertised, extremely satisfied with this order.",
    ),
    (
        "I would not recommend this seller, the item arrived damaged and late.",
        "I wouldn't suggest buying from this vendor, the product showed up broken and behind schedule.",
    ),
    (
        "Good value for the price, works as expected with no issues so far.",
        "Decent value for the cost, functions as anticipated with no problems yet.",
    ),
]

# Length-robustness check: appending neutral, meaning-irrelevant filler
# should NOT push the fake-probability in one consistent direction.
LENGTH_BASE = "The product works fine and arrived on time."
LENGTH_FILLERS = [
    "",
    " I ordered it last week.",
    " I ordered it last week, and it came in a small box.",
    " I ordered it last week, and it came in a small box with a printed receipt inside.",
]


def load_model(model_dir: Path):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    return tokenizer, model, device


@torch.no_grad()
def fake_probability(tokenizer, model, device, text: str) -> float:
    enc = tokenizer(text, truncation=True, max_length=256, return_tensors="pt").to(device)
    logits = model(**enc).logits
    probs = torch.softmax(logits, dim=1)[0]
    return float(probs[1].item())  # index 1 = FAKE, per label_mapping in training script


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=str, default=str(Path(__file__).resolve().parents[2] / "models" / "fake_review_detector"))
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    print(f"Loading model from {model_dir}")
    tokenizer, model, device = load_model(model_dir)
    print(f"Device: {device}\n")

    print("=== Paraphrase-stability test (meaning-preserving synonym substitution) ===")
    diffs = []
    flips = 0
    for i, (a, b) in enumerate(PARAPHRASE_PAIRS, 1):
        pa = fake_probability(tokenizer, model, device, a)
        pb = fake_probability(tokenizer, model, device, b)
        diff = abs(pa - pb)
        diffs.append(diff)
        decision_flip = (pa >= 0.5) != (pb >= 0.5)
        flips += int(decision_flip)
        print(f"[{i}] P(fake) original={pa:.4f}  paraphrase={pb:.4f}  |diff|={diff:.4f}  decision_flip={decision_flip}")
        print(f"    A: {a}")
        print(f"    B: {b}")

    print(f"\nMean |diff| across {len(PARAPHRASE_PAIRS)} pairs: {sum(diffs) / len(diffs):.4f}")
    print(f"Max |diff|: {max(diffs):.4f}")
    print(f"Decision flips (crossed 0.5 threshold on meaning-preserving reword): {flips}/{len(PARAPHRASE_PAIRS)}")

    print("\n=== Length-robustness check (appending neutral filler) ===")
    length_probs = [fake_probability(tokenizer, model, device, LENGTH_BASE + f) for f in LENGTH_FILLERS]
    for f, p in zip(LENGTH_FILLERS, length_probs):
        print(f"len={len(LENGTH_BASE + f):3d}  P(fake)={p:.4f}  text={(LENGTH_BASE + f)!r}")
    length_spread = max(length_probs) - min(length_probs)
    print(f"Spread across filler lengths: {length_spread:.4f}")

    print("\n=== Verdict ===")
    mean_diff = sum(diffs) / len(diffs)
    if flips == 0 and mean_diff < 0.15 and length_spread < 0.15:
        print("PASS: predictions are stable under meaning-preserving paraphrasing and length variation.")
    else:
        print("FAIL: predictions are NOT stable -- do not ship this checkpoint as a reliable signal.")


if __name__ == "__main__":
    main()
