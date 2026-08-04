#!/usr/bin/env python
"""Discover, validate, and standardize model/tokenizer artifacts.

Usage:
    python export_artifacts.py --discover
    python export_artifacts.py --bert-model path/to/bert_directory --cnn-checkpoint path/to/cnn2d_checkpoint.pt --cnn-tokenizer path/to/cnn2d_tokenizer.pkl

Never fabricates weights or a tokenizer. Fails clearly when a genuine
artifact is unavailable, rather than silently skipping validation.
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import torch  # noqa: E402

from app.ml.models import CNN2DReviewSentiment  # noqa: E402
from app.ml.utils import write_json  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent

ARTIFACT_GLOBS = ["*.pt", "*.pth", "*.ckpt", "*.bin", "*.safetensors", "*.pkl", "*.pickle", "*.joblib", "*.npy", "*.npz"]


def discover(root: Path) -> list[dict]:
    found = []
    for pattern in ARTIFACT_GLOBS:
        for path in root.rglob(pattern):
            if "node_modules" in path.parts or ".git" in path.parts:
                continue
            found.append({"path": str(path.relative_to(root)), "size_mb": round(path.stat().st_size / 1024**2, 3), "suffix": path.suffix})
    return sorted(found, key=lambda x: -x["size_mb"])


def validate_cnn_checkpoint(checkpoint_path: Path) -> dict:
    state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model = CNN2DReviewSentiment()
    result = model.load_state_dict(state_dict, strict=True)
    total_params = sum(p.numel() for p in model.parameters())
    return {
        "path": str(checkpoint_path), "strict_load_result": str(result),
        "total_params": total_params, "n_state_dict_keys": len(state_dict),
        "embedding_shape": list(model.embedding.weight.shape),
        "output_layer_shape": list(model.output_layer.weight.shape),
    }


def validate_cnn_tokenizer(tokenizer_path: Path) -> dict:
    import __main__ as main_module
    from app.ml.preprocessing import SimpleVocabTokenizer

    main_module.SimpleVocabTokenizer = SimpleVocabTokenizer
    with open(tokenizer_path, "rb") as f:
        tok = pickle.load(f)
    return {
        "path": str(tokenizer_path), "type": type(tok).__name__,
        "vocab_size": tok.vocab_size, "max_index": tok.max_index,
        "oov_index": tok.word_index.get(tok.oov_token), "num_words_limit": tok.num_words,
    }


def validate_bert_directory(model_dir: Path) -> dict:
    from transformers import AutoConfig

    config = AutoConfig.from_pretrained(str(model_dir))
    weight_files = [f for f in ["model.safetensors", "pytorch_model.bin"] if (model_dir / f).is_file()]
    return {
        "path": str(model_dir), "architectures": config.architectures,
        "num_labels": config.num_labels, "id2label": config.id2label,
        "weight_files_present": weight_files, "vocab_size": getattr(config, "vocab_size", None),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and validate model artifacts.")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--bert-model", default=None)
    parser.add_argument("--cnn-checkpoint", default=None)
    parser.add_argument("--cnn-tokenizer", default=None)
    args = parser.parse_args()

    report: dict = {}

    if args.discover:
        found = discover(PROJECT_ROOT)
        report["discovered_artifacts"] = found
        print(f"Discovered {len(found)} candidate artifact files under {PROJECT_ROOT}")
        for item in found[:20]:
            print(f"  {item['size_mb']:>10.2f} MB  {item['path']}")

    bert_model = Path(args.bert_model) if args.bert_model else PROJECT_ROOT / "models" / "bert_review_sentiment"
    cnn_checkpoint = Path(args.cnn_checkpoint) if args.cnn_checkpoint else PROJECT_ROOT / "models" / "cnn2d_review_sentiment.pt"
    cnn_tokenizer = Path(args.cnn_tokenizer) if args.cnn_tokenizer else PROJECT_ROOT / "artifacts" / "cnn2d_tokenizer.pkl"

    if bert_model.is_dir():
        report["bert"] = validate_bert_directory(bert_model)
        print(f"BERT OK: {report['bert']}")
    else:
        print(f"[FAIL] BERT directory not found at {bert_model}")

    if cnn_checkpoint.is_file():
        report["cnn2d_checkpoint"] = validate_cnn_checkpoint(cnn_checkpoint)
        print(f"CNN2D checkpoint OK: strict load = {report['cnn2d_checkpoint']['strict_load_result']}")
    else:
        print(f"[FAIL] CNN2D checkpoint not found at {cnn_checkpoint}")

    if cnn_tokenizer.is_file():
        report["cnn2d_tokenizer"] = validate_cnn_tokenizer(cnn_tokenizer)
        print(f"CNN2D tokenizer OK: vocab_size={report['cnn2d_tokenizer']['vocab_size']}")
    else:
        print(f"[FAIL] CNN2D tokenizer not found at {cnn_tokenizer}")

    write_json(PROJECT_ROOT / "results" / "artifact_export_report.json", report)
    print(f"\nSaved report to {PROJECT_ROOT / 'results' / 'artifact_export_report.json'}")


if __name__ == "__main__":
    main()
