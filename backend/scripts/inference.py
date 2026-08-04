#!/usr/bin/env python
"""Real-time single-review sentiment inference from the command line.

Usage:
    python inference.py --text "The product arrived early and works perfectly."
    python inference.py --file review.txt --model cnn2d
    python inference.py --text "O produto chegou rapido" --source-language pt --translate

Fixes the notebook's inference-cell bugs (cell 149): loads the verified
fine-tuned BERT directory (not a nonexistent output/bert_sentiment_model.pt
raw state dict), never falls back to a fresh untrained classifier, and never
reuses the Marian translation tokenizer for sentiment classification.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.exceptions import AppError  # noqa: E402
from app.ml.models import load_cnn2d_model, load_fine_tuned_bert  # noqa: E402
from app.ml.utils import get_device  # noqa: E402
from app.services.model_registry import ModelRegistry  # noqa: E402
from app.services.sentiment_service import predict_sentiment  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent


def build_registry(model_name: str, model_path: str | None, checkpoint: str | None, tokenizer_path: str | None, device: str) -> ModelRegistry:
    """Loads ONLY the requested model, so `--model cnn2d` never requires BERT to be present."""
    import pickle

    registry = ModelRegistry()
    registry.device = device
    if model_name == "bert":
        path = Path(model_path) if model_path else PROJECT_ROOT / "models" / "bert_review_sentiment"
        registry.bert_model, registry.bert_tokenizer = load_fine_tuned_bert(path, device=device)
    else:
        import __main__ as main_module
        from app.ml.preprocessing import SimpleVocabTokenizer

        main_module.SimpleVocabTokenizer = SimpleVocabTokenizer
        ckpt = Path(checkpoint) if checkpoint else PROJECT_ROOT / "models" / "cnn2d_review_sentiment.pt"
        tok = Path(tokenizer_path) if tokenizer_path else PROJECT_ROOT / "artifacts" / "cnn2d_tokenizer.pkl"
        registry.cnn_model = load_cnn2d_model(ckpt, device=device)
        with open(tok, "rb") as f:
            registry.cnn_tokenizer = pickle.load(f)
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Run sentiment inference on a single review.")
    parser.add_argument("--text", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--model", choices=["bert", "cnn2d"], default="bert")
    parser.add_argument("--model-path", default=None, help="BERT model directory (default: models/bert_review_sentiment)")
    parser.add_argument("--checkpoint", default=None, help="CNN2D checkpoint path (default: models/cnn2d_review_sentiment.pt)")
    parser.add_argument("--tokenizer", default=None, help="CNN2D tokenizer path (default: artifacts/cnn2d_tokenizer.pkl)")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default=None)
    parser.add_argument("--source-language", choices=["en", "pt"], default="en")
    parser.add_argument("--translate", action="store_true")
    args = parser.parse_args()

    if not args.text and not args.file:
        parser.error("Provide --text or --file")

    text = args.text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")

    device = args.device or str(get_device())
    try:
        registry = build_registry(args.model, args.model_path, args.checkpoint, args.tokenizer, device)
        result = predict_sentiment(registry, text, model_name=args.model, source_language=args.source_language, translate=args.translate)
    except AppError as e:
        print(f"Error [{e.code}]: {e.message}", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
