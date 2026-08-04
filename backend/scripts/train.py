#!/usr/bin/env python
"""Train BERT or CNN2D on the corrected, deduplicated sentiment split.

Usage:
    python train.py --data-dir data/raw --model bert --epochs 3 --batch-size 8 --learning-rate 2e-5
    python train.py --data-dir data/raw --model cnn2d --epochs 10 --batch-size 64 --learning-rate 0.001

Never runs automatically on import, never exposed as an API endpoint. Loads
(or builds) the translated-review dataset, removes neutral/empty reviews,
deduplicates BEFORE splitting, resolves conflicting labels, creates a
reproducible stratified split, saves the split manifest, fits preprocessing
artifacts on TRAIN ONLY, trains with early stopping, reloads the best
weights, evaluates on the untouched test set, and saves metrics.
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # noqa: E402
import torch  # noqa: E402

from app.ml import datasets as ds  # noqa: E402
from app.ml import evaluation as ev  # noqa: E402
from app.ml import models as ml_models  # noqa: E402
from app.ml import preprocessing as prep  # noqa: E402
from app.ml import training as trn  # noqa: E402
from app.ml.translation import DEFAULT_CACHE_PATH  # noqa: E402
from app.ml.utils import get_device, set_seed, write_json  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent


def load_reviews_dataset(data_dir: Path) -> pd.DataFrame:
    """Load review text for the sentiment task: the translated-review cache if present,
    otherwise raise (translation must be run first via translate_reviews.py)."""
    cache_path = PROJECT_ROOT / DEFAULT_CACHE_PATH
    if cache_path.is_file():
        return pd.read_csv(cache_path)
    raise FileNotFoundError(
        f"No translated-review cache found at {cache_path}. Run translate_reviews.py first, "
        f"or place raw Olist CSVs under {data_dir} and run run_pipeline.py --clean --translate."
    )


def build_split(seed: int):
    reviews = load_reviews_dataset(PROJECT_ROOT / "data" / "raw")
    sent_df = prep.build_sentiment_dataframe(reviews)
    deduped, dedupe_report = prep.remove_duplicate_reviews(sent_df)
    split = prep.split_sentiment_dataset(deduped, seed=seed)
    overlap = split.overlap_report()
    print(f"Dataset sizes -> train: {len(split.train):,} val: {len(split.val):,} test: {len(split.test):,}")
    print(f"Class distribution (train): {split.train['label'].value_counts().to_dict()}")
    print(f"Deduplication: {dedupe_report.to_dict()}")
    print(f"Split overlap (must be all zero): {overlap}")
    assert all(v == 0 for v in overlap["normalized_text_overlap"].values()), "Text leakage detected across splits!"
    return split, dedupe_report, overlap


def train_bert_cmd(args: argparse.Namespace) -> None:
    set_seed(args.seed)
    device = get_device()
    print(f"Device: {device}")

    split, dedupe_report, overlap = build_split(args.seed)
    prep.save_split_manifest(
        split, PROJECT_ROOT / "artifacts" / "split_manifest.json", seed=args.seed,
        dedupe_rule="normalize -> drop conflicting labels -> drop duplicate normalized text -> stratified split",
        source_dataset=str(PROJECT_ROOT / DEFAULT_CACHE_PATH),
    )

    model = ml_models.create_bert_model()
    model.to(device)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Trainable parameters: {total_params:,}")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(ml_models.BERT_BASE_CHECKPOINT)
    train_loader = ds.build_bert_dataloader(split.train["text"].tolist(), split.train["label"].tolist(), tokenizer, args.max_len, args.batch_size, shuffle=True)
    val_loader = ds.build_bert_dataloader(split.val["text"].tolist(), split.val["label"].tolist(), tokenizer, args.max_len, args.batch_size, shuffle=False)
    test_loader = ds.build_bert_dataloader(split.test["text"].tolist(), split.test["label"].tolist(), tokenizer, args.max_len, args.batch_size, shuffle=False)

    checkpoint_dir = PROJECT_ROOT / "weights"
    best_state, history, train_time, best_epoch = trn.train_bert(
        model, train_loader, val_loader, device, epochs=args.epochs, lr=args.learning_rate,
        early_stopping_patience=args.early_stopping_patience, checkpoint_dir=str(checkpoint_dir),
    )
    if best_state is not None:
        model.load_state_dict(best_state)
    print(f"Best epoch: {best_epoch}. Total training time: {train_time:.1f}s")

    y_true, y_pred, y_prob = ev.get_bert_predictions(model, test_loader)
    test_metrics = ev.evaluate_classification(y_true, y_pred, y_prob)
    print("Test metrics:", test_metrics.to_dict())

    out_dir = PROJECT_ROOT / "models" / "bert_review_sentiment"
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"Saved fine-tuned BERT to {out_dir}")

    write_json(PROJECT_ROOT / "results" / "bert_training_run.json", {
        "history": history.to_dict(), "best_epoch": best_epoch, "train_time_seconds": train_time,
        "test_metrics": test_metrics.to_dict(), "dedupe_report": dedupe_report.to_dict(), "split_overlap": overlap,
    })


def train_cnn2d_cmd(args: argparse.Namespace) -> None:
    import numpy as np
    from sklearn.utils.class_weight import compute_class_weight

    set_seed(args.seed)
    device = get_device()
    print(f"Device: {device}")

    split, dedupe_report, overlap = build_split(args.seed)
    prep.save_split_manifest(
        split, PROJECT_ROOT / "artifacts" / "split_manifest.json", seed=args.seed,
        dedupe_rule="normalize -> drop conflicting labels -> drop duplicate normalized text -> stratified split",
        source_dataset=str(PROJECT_ROOT / DEFAULT_CACHE_PATH),
    )

    tokenizer = prep.SimpleVocabTokenizer(num_words=args.max_words, oov_token="<OOV>")
    tokenizer.fit_on_texts(split.train["text"])  # TRAIN ONLY
    print(f"CNN vocabulary size: {tokenizer.vocab_size:,}")

    X_train_seq = ds.encode_texts_for_cnn(split.train["text"], tokenizer, args.max_len)
    X_val_seq = ds.encode_texts_for_cnn(split.val["text"], tokenizer, args.max_len)
    X_test_seq = ds.encode_texts_for_cnn(split.test["text"], tokenizer, args.max_len)

    train_loader = ds.build_cnn_dataloader(X_train_seq, split.train["label"], args.batch_size, shuffle=True)
    val_loader = ds.build_cnn_dataloader(X_val_seq, split.val["label"], args.batch_size, shuffle=False)
    test_loader = ds.build_cnn_dataloader(X_test_seq, split.test["label"], args.batch_size, shuffle=False)

    class_weights = compute_class_weight("balanced", classes=np.unique(split.train["label"]), y=split.train["label"].values)
    class_weights_tensor = torch.tensor(class_weights, dtype=torch.float32)

    model = ml_models.CNN2DReviewSentiment(vocab_size=args.max_words, max_len=args.max_len).to(device)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Trainable parameters: {total_params:,}")

    best_state, history, train_time, best_epoch = trn.train_cnn2d(
        model, train_loader, val_loader, device, class_weights_tensor,
        epochs=args.epochs, lr=args.learning_rate, early_stopping_patience=args.early_stopping_patience,
    )
    if best_state is not None:
        model.load_state_dict(best_state)
    print(f"Best epoch: {best_epoch}. Total training time: {train_time:.1f}s")

    y_true, y_pred, y_prob = ev.get_cnn_predictions(model, test_loader)
    test_metrics = ev.evaluate_classification(y_true, y_pred, y_prob)
    print("Test metrics:", test_metrics.to_dict())

    model_path = PROJECT_ROOT / "models" / "cnn2d_review_sentiment.pt"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), model_path)
    tok_path = PROJECT_ROOT / "artifacts" / "cnn2d_tokenizer.pkl"
    with open(tok_path, "wb") as f:
        pickle.dump(tokenizer, f)
    print(f"Saved CNN2D model to {model_path} and tokenizer to {tok_path}")

    write_json(PROJECT_ROOT / "results" / "cnn2d_training_run.json", {
        "history": history.to_dict(), "best_epoch": best_epoch, "train_time_seconds": train_time,
        "test_metrics": test_metrics.to_dict(), "vocab_size": tokenizer.vocab_size,
        "dedupe_report": dedupe_report.to_dict(), "split_overlap": overlap,
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the BERT or CNN2D sentiment model.")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--model", choices=["bert", "cnn2d"], required=True)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--learning-rate", type=float, default=None)
    parser.add_argument("--max-len", type=int, default=None)
    parser.add_argument("--max-words", type=int, default=30000)
    parser.add_argument("--early-stopping-patience", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.model == "bert":
        args.epochs = args.epochs or trn.BERT_EPOCHS
        args.batch_size = args.batch_size or 8
        args.learning_rate = args.learning_rate or trn.BERT_LEARNING_RATE
        args.max_len = args.max_len or 128
        args.early_stopping_patience = args.early_stopping_patience or trn.BERT_EARLY_STOPPING_PATIENCE
        start = time.time()
        train_bert_cmd(args)
        print(f"Total wall time: {time.time() - start:.1f}s")
    else:
        args.epochs = args.epochs or trn.CNN_EPOCHS
        args.batch_size = args.batch_size or 64
        args.learning_rate = args.learning_rate or trn.CNN_LR
        args.max_len = args.max_len or 100
        args.early_stopping_patience = args.early_stopping_patience or trn.CNN_EARLY_STOPPING_PATIENCE
        start = time.time()
        train_cnn2d_cmd(args)
        print(f"Total wall time: {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
