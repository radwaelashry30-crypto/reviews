#!/usr/bin/env python
"""Systematic diagnostic: on what basis does the SHIPPED fake-review model
(jb10231/fake-review-detector) actually decide a review is "fake"?

Not a re-run of the paraphrase-instability test (already established, see
app/ml/fake_review_detection.py's module docstring) -- this probes for any
identifiable textual property that correlates with a high fake_probability,
by varying one property at a time across matched review pairs/groups:
length, sentiment polarity, specificity/genericness, register (casual vs
formal), punctuation/exclamation intensity, and presence of first-person
personal detail. If a real pattern exists, it should show up as a
consistent shift across these controlled groups. If confidence swings
around with no consistent direction across any of them, that itself is the
finding -- worth stating precisely in an abstract instead of guessing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.fake_review_detection import load_fake_review_pipeline, score_single_review  # noqa: E402


def show(label: str, text: str, pipe) -> float:
    r = score_single_review(pipe, text)
    fp = r.get("fake_probability", float("nan"))
    print(f"  [{label}] fake_prob={fp:.4f}  raw_label={r.get('raw_label')}  raw_conf={r.get('raw_confidence')}")
    print(f"      text: {text!r}")
    return fp


def main() -> None:
    print("Loading jb10231/fake-review-detector...")
    pipe = load_fake_review_pipeline(device=-1)
    print("Loaded.\n")

    print("=== A. Length (same content, progressively longer, meaning unchanged) ===")
    base = "Great product, works exactly as described."
    fillers = [
        "", " Shipping was quick too.", " Shipping was quick too, and the packaging was solid.",
        " Shipping was quick too, and the packaging was solid, arrived two days early which was a nice surprise.",
    ]
    a_scores = [show(f"len={len(base+f)}", base + f, pipe) for f in fillers]
    print()

    print("=== B. Sentiment polarity (same topic, positive vs negative vs neutral) ===")
    b_scores = {
        "positive": show("positive", "The blender is fantastic, blends everything smoothly and cleans up in seconds.", pipe),
        "negative": show("negative", "The blender is terrible, leaks everywhere and the blade jammed on day one.", pipe),
        "neutral": show("neutral", "The blender does what it says, nothing special but nothing wrong either.", pipe),
    }
    print()

    print("=== C. Specificity (generic praise vs detailed personal account) ===")
    c_scores = {
        "generic": show("generic", "This is a great product. I highly recommend it. Five stars.", pipe),
        "specific": show("specific", "I bought this for my daughter's birthday last March, and the zipper on the left pocket already broke after three uses.", pipe),
    }
    print()

    print("=== D. Register (casual/slangy vs formal/marketing-speak) ===")
    d_scores = {
        "casual": show("casual", "ngl this thing kinda slaps, works great no cap", pipe),
        "formal": show("formal", "This product significantly exceeds expectations in terms of build quality and overall performance.", pipe),
    }
    print()

    print("=== E. Punctuation / exclamation intensity ===")
    e_scores = {
        "plain": show("plain", "This is a good vacuum cleaner and it works well.", pipe),
        "excited": show("excited", "This is an AMAZING vacuum cleaner!!! It works SO well!!! Best purchase EVER!!!", pipe),
    }
    print()

    print("=== F. First-person personal detail vs impersonal statement ===")
    f_scores = {
        "personal": show("personal", "My cat knocked this off the shelf twice and it still works fine, I'm impressed.", pipe),
        "impersonal": show("impersonal", "The product is durable and withstands accidental drops without damage.", pipe),
    }
    print()

    print("=== Summary: any consistent direction? ===")
    print(f"A. Length: {[round(s, 3) for s in a_scores]}  (monotonic? {a_scores == sorted(a_scores) or a_scores == sorted(a_scores, reverse=True)})")
    print(f"B. Sentiment: {b_scores}")
    print(f"C. Specificity: {c_scores}")
    print(f"D. Register: {d_scores}")
    print(f"E. Punctuation: {e_scores}")
    print(f"F. Personal detail: {f_scores}")


if __name__ == "__main__":
    main()
