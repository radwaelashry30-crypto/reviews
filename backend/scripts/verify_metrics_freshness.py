#!/usr/bin/env python
"""CI guard: fails if results/reproduced_metrics.json's recorded BERT
checkpoint fingerprint doesn't match the checkpoint actually committed at
models/bert_review_sentiment/. This is the exact bug in Technical Review
#03 -- a retraining run silently overwrote the checkpoint without
regenerating the metrics that describe it, so every published number (and
the "which model is better" conclusion) went stale relative to what's
actually shipped. Same check runs at app startup (app/main.py's
_check_metrics_freshness) as a runtime warning; this is the CI-time hard
gate that should have caught it before merge.

Usage:
    python scripts/verify_metrics_freshness.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
PROJECT_ROOT = BACKEND_DIR.parent

from app.ml.utils import checkpoint_fingerprint  # noqa: E402


def main() -> int:
    metrics_path = PROJECT_ROOT / "results" / "reproduced_metrics.json"
    bert_path = PROJECT_ROOT / "models" / "bert_review_sentiment"

    if not metrics_path.is_file():
        print(f"No {metrics_path} to check -- skipping (nothing published yet).")
        return 0
    if not bert_path.is_dir():
        print(f"No checkpoint at {bert_path} -- skipping (nothing to compare against).")
        return 0

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    recorded = metrics.get("bert", {}).get("checkpoint_sha256")
    current = checkpoint_fingerprint(bert_path)

    if not recorded:
        print("results/reproduced_metrics.json has no recorded checkpoint_sha256 -- run scripts/regenerate_metrics.py.", file=sys.stderr)
        return 1
    if recorded != current:
        print(
            f"STALE METRICS: results/reproduced_metrics.json describes checkpoint {recorded}, "
            f"but models/bert_review_sentiment/ is currently {current}. Run:\n"
            f"    cd backend && python scripts/regenerate_metrics.py",
            file=sys.stderr,
        )
        return 1

    print(f"OK: reproduced_metrics.json matches the current BERT checkpoint ({current}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
