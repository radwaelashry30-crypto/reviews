#!/usr/bin/env python
"""Translate Portuguese review text to English, reusing any existing checkpoint.

Usage:
    python translate_reviews.py --input data/raw/olist_order_reviews_dataset.csv --batch-size 32

Never downloads the translation model at import time -- only when this
script actually runs the translation step (and reuses data/interim/reviews_translated.csv
if it already has a translation for a given row).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # noqa: E402

from app.ml.translation import ACTUAL_TRANSLATION_MODEL, DEFAULT_CACHE_PATH, translate_reviews  # noqa: E402
from app.ml.utils import write_json  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate review_comment_message (pt) -> review_comment_message_en.")
    parser.add_argument("--input", default=None, help="Raw olist_order_reviews_dataset.csv (used only if no checkpoint exists yet)")
    parser.add_argument("--checkpoint", default=str(PROJECT_ROOT / DEFAULT_CACHE_PATH))
    parser.add_argument("--model", default=ACTUAL_TRANSLATION_MODEL)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    checkpoint_path = Path(args.checkpoint)
    if checkpoint_path.is_file():
        reviews = pd.read_csv(checkpoint_path)
        print(f"Resuming from existing checkpoint: {checkpoint_path} ({len(reviews):,} rows)")
    elif args.input:
        reviews = pd.read_csv(args.input)
        print(f"Starting fresh from {args.input} ({len(reviews):,} rows)")
    else:
        raise SystemExit(f"No existing checkpoint at {checkpoint_path} and no --input given.")

    translated, manifest = translate_reviews(
        reviews, model_name=args.model, batch_size=args.batch_size,
        max_length=args.max_length, checkpoint_path=checkpoint_path, device=args.device,
    )
    write_json(PROJECT_ROOT / "artifacts" / "translation_manifest.json", manifest.to_dict())
    print(f"Translated {manifest.rows_translated:,} rows ({manifest.rows_failed:,} failures). Saved to {checkpoint_path}")


if __name__ == "__main__":
    main()
