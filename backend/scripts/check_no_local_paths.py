#!/usr/bin/env python
"""CI guard: fails if any committed file under results/, artifacts/, or
config/ contains a local machine-specific filesystem path (Windows user
profile or Unix home directory). Exists because a real one leaked into
results/cnn2d_negation_augmentation_report.json once already -- both a
reproducibility problem (nobody else can resolve that path) and a minor
privacy leak (system username, local folder structure). See Technical
Review #17.

Usage:
    python scripts/check_no_local_paths.py
Exit code 0 = clean, 1 = leaked path(s) found (printed to stderr).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKED_DIRS = ["results", "artifacts", "config"]
PATTERN = re.compile(r"[A-Za-z]:\\\\Users\\|/home/[a-zA-Z0-9_]+/|/Users/[a-zA-Z0-9_]+/")


def main() -> int:
    leaks: list[tuple[Path, int, str]] = []
    for dirname in CHECKED_DIRS:
        base = PROJECT_ROOT / dirname
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".json", ".yaml", ".yml", ".txt", ".md"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if PATTERN.search(line):
                    leaks.append((path.relative_to(PROJECT_ROOT), lineno, line.strip()[:120]))

    if leaks:
        print("Local machine-specific paths found in committed files:", file=sys.stderr)
        for path, lineno, snippet in leaks:
            print(f"  {path}:{lineno}: {snippet}", file=sys.stderr)
        return 1

    print("OK: no local paths found in results/, artifacts/, config/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
