#!/usr/bin/env python
"""Evaluate an already-trained model against the stored split manifest. Never retrains.

Usage:
    python evaluate.py --model bert --model-path models/bert_review_sentiment --split-manifest artifacts/split_manifest.json
    python evaluate.py --model cnn2d --checkpoint models/cnn2d_review_sentiment.pt --tokenizer artifacts/cnn2d_tokenizer.pkl --split-manifest artifacts/split_manifest.json
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # noqa: E402

from app.ml import datasets as ds  # noqa: E402
from app.ml import evaluation as ev  # noqa: E402
from app.ml import models as ml_models  # noqa: E402
from app.ml import preprocessing as prep  # noqa: E402
from app.ml.utils import get_device, write_json  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent


def _manifest_split_to_frame(manifest: dict, name: str) -> pd.DataFrame:
    return pd.DataFrame(manifest["splits"][name])


def evaluate_bert(model_path: Path, manifest: dict, source_texts: pd.DataFrame, max_len: int = 128, batch_size: int = 8) -> dict:
    model, tokenizer = ml_models.load_fine_tuned_bert(model_path, device=get_device())
    results = {}
    for split_name in ["val", "test"]:
        rows = _manifest_split_to_frame(manifest, split_name)
        merged = rows.merge(source_texts[["text_hash", "text"]].drop_duplicates("text_hash"), on="text_hash", how="left")
        loader = ds.build_bert_dataloader(merged["text"].tolist(), merged["label"].tolist(), tokenizer, max_len, batch_size, shuffle=False)
        y_true, y_pred, y_prob = ev.get_bert_predictions(model, loader)
        metrics = ev.evaluate_classification(y_true, y_pred, y_prob)
        results[split_name] = {
            "metrics": metrics.to_dict(),
            "confusion_matrix": ev.confusion_matrix_dict(y_true, y_pred),
            "classification_report": ev.classification_report_dict(y_true, y_pred),
        }
        print(f"BERT {split_name}: {metrics.to_dict()}")
    return results


def evaluate_cnn2d(checkpoint_path: Path, tokenizer_path: Path, manifest: dict, source_texts: pd.DataFrame, max_len: int = 100, batch_size: int = 64) -> dict:
    import __main__ as main_module
    from app.ml.preprocessing import SimpleVocabTokenizer

    main_module.SimpleVocabTokenizer = SimpleVocabTokenizer  # match the artifact's pickled __main__ reference
    model = ml_models.load_cnn2d_model(checkpoint_path, device=get_device())
    with open(tokenizer_path, "rb") as f:
        tokenizer = pickle.load(f)

    results = {}
    for split_name in ["val", "test"]:
        rows = _manifest_split_to_frame(manifest, split_name)
        merged = rows.merge(source_texts[["text_hash", "text"]].drop_duplicates("text_hash"), on="text_hash", how="left")
        X_seq = ds.encode_texts_for_cnn(merged["text"], tokenizer, max_len)
        loader = ds.build_cnn_dataloader(X_seq, merged["label"], batch_size, shuffle=False)
        y_true, y_pred, y_prob = ev.get_cnn_predictions(model, loader)
        metrics = ev.evaluate_classification(y_true, y_pred, y_prob)
        results[split_name] = {
            "metrics": metrics.to_dict(),
            "confusion_matrix": ev.confusion_matrix_dict(y_true, y_pred),
            "classification_report": ev.classification_report_dict(y_true, y_pred),
        }
        print(f"CNN2D {split_name}: {metrics.to_dict()}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained sentiment model against the stored split manifest.")
    parser.add_argument("--model", choices=["bert", "cnn2d"], required=True)
    parser.add_argument("--model-path", default=str(PROJECT_ROOT / "models" / "bert_review_sentiment"))
    parser.add_argument("--checkpoint", default=str(PROJECT_ROOT / "models" / "cnn2d_review_sentiment.pt"))
    parser.add_argument("--tokenizer", default=str(PROJECT_ROOT / "artifacts" / "cnn2d_tokenizer.pkl"))
    parser.add_argument("--split-manifest", default=str(PROJECT_ROOT / "artifacts" / "split_manifest.json"))
    parser.add_argument("--source-texts", default=str(PROJECT_ROOT / "data" / "interim" / "reviews_translated.csv"),
                         help="CSV with review_comment_message_en, used to resolve text_hash -> text for the stored split.")
    args = parser.parse_args()

    manifest = prep.load_split_manifest(args.split_manifest)
    print(f"Loaded split manifest (seed={manifest['seed']}, sizes={manifest['sizes']})")

    reviews = pd.read_csv(args.source_texts)
    sent_df = prep.build_sentiment_dataframe(reviews)

    if args.model == "bert":
        results = evaluate_bert(Path(args.model_path), manifest, sent_df)
        write_json(PROJECT_ROOT / "results" / "evaluate_bert_run.json", results)
    else:
        results = evaluate_cnn2d(Path(args.checkpoint), Path(args.tokenizer), manifest, sent_df)
        write_json(PROJECT_ROOT / "results" / "evaluate_cnn2d_run.json", results)


if __name__ == "__main__":
    main()
