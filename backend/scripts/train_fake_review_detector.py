#!/usr/bin/env python
"""Fine-tunes a DistilBERT fake-review detector on a real, documented, labeled
dataset -- replacing the unverified external checkpoint (jb10231/fake-review-
detector).

Why this exists: `jb10231/fake-review-detector`'s label semantics were never
verified (its config.json exposes only LABEL_0/LABEL_1, not FAKE/REAL), and
direct testing proved its predictions unstable under meaning-preserving
paraphrasing (a pure synonym substitution flipped a verdict from 99.9% to
0.1% confidence -- see MODEL_COMPARISON_AUDIT.md and
app/ml/fake_review_detection.py's module docstring). No non-training fix was
possible for a defect that lives inside a third-party checkpoint we don't
control.

Dataset: `theArijitDas/Fake-Reviews-Dataset` (HuggingFace Hub, no auth
required) -- 40,526 Amazon product reviews across 10 categories, label 0 =
genuine human-written review, label 1 = GPT-2-generated review. This is the
SAME task framing the original model's own model card claimed ("FAKE" =
AI-generated, "REAL" = genuine human review) -- not a scope change, a
faithful, verifiable replacement for an unverifiable one.

Honest scoping: this detects AI-generated review TEXT vs human-written text.
It is not a general "deceptive intent" detector -- a human can write a
misleading review without AI assistance, and this model has no signal for
that. This is stated explicitly in the shipped disclaimer.

Usage:
    python scripts/train_fake_review_detector.py --epochs 2 --batch-size 16
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml.utils import get_device, set_seed, write_json  # noqa: E402

BASE_CHECKPOINT = "distilbert-base-uncased"
MAX_LEN = 256
LABEL_MAPPING = {"REAL": 0, "FAKE": 1}


def load_dataset_df(seed: int) -> pd.DataFrame:
    from datasets import load_dataset

    ds = load_dataset("theArijitDas/Fake-Reviews-Dataset")
    df = ds["train"].to_pandas()
    df = df.dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() > 0]
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    df["label"] = df["label"].astype(int)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def split_dataset(df: pd.DataFrame, seed: int):
    from sklearn.model_selection import train_test_split

    X_temp, X_test, y_temp, y_test = train_test_split(
        df["text"], df["label"], test_size=0.20, random_state=seed, stratify=df["label"],
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=0.125, random_state=seed, stratify=y_temp,
    )
    return X_train, X_val, X_test, y_train, y_val, y_test


class ReviewDataset(torch.utils.data.Dataset):
    def __init__(self, texts, labels):
        self.texts = list(texts)
        self.labels = list(labels)

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return self.texts[idx], int(self.labels[idx])


def make_collate_fn(tokenizer, max_len: int):
    def collate(batch):
        texts, labels = zip(*batch)
        enc = tokenizer(list(texts), max_length=max_len, padding=True, truncation=True, return_tensors="pt")
        enc["labels"] = torch.tensor(labels, dtype=torch.long)
        return enc
    return collate


def run_epoch(model, loader, device, optimizer=None, scheduler=None):
    is_train = optimizer is not None
    model.train() if is_train else model.eval()
    total_loss, correct, total = 0.0, 0, 0
    with torch.set_grad_enabled(is_train):
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            loss = outputs.loss
            if is_train:
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
            preds = torch.argmax(outputs.logits, dim=1)
            correct += (preds == batch["labels"]).sum().item()
            total += batch["labels"].size(0)
            total_loss += loss.item() * batch["labels"].size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def get_predictions(model, loader, device):
    model.eval()
    all_labels, all_preds, all_probs = [], [], []
    for batch in loader:
        labels = batch["labels"]
        inputs = {k: v.to(device) for k, v in batch.items() if k != "labels"}
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=1)[:, 1]
        preds = torch.argmax(logits, dim=1)
        all_labels.append(labels.numpy())
        all_preds.append(preds.cpu().numpy())
        all_probs.append(probs.cpu().numpy())
    return np.concatenate(all_labels), np.concatenate(all_preds), np.concatenate(all_probs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    device = get_device()
    print(f"Device: {device}")

    print("=== Loading theArijitDas/Fake-Reviews-Dataset (HuggingFace Hub, no auth) ===")
    df = load_dataset_df(args.seed)
    print(f"Rows after dedup: {len(df)} (label balance: {df['label'].value_counts(normalize=True).to_dict()})")

    X_train, X_val, X_test, y_train, y_val, y_test = split_dataset(df, args.seed)
    print(f"Split -- train: {len(X_train)}  val: {len(X_val)}  test: {len(X_test)}")

    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

    tokenizer = AutoTokenizer.from_pretrained(BASE_CHECKPOINT)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_CHECKPOINT, num_labels=2)
    model.config.id2label = {0: "REAL", 1: "FAKE"}
    model.config.label2id = {"REAL": 0, "FAKE": 1}
    model.to(device)

    collate_fn = make_collate_fn(tokenizer, MAX_LEN)
    train_loader = torch.utils.data.DataLoader(ReviewDataset(X_train, y_train), batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)
    val_loader = torch.utils.data.DataLoader(ReviewDataset(X_val, y_val), batch_size=args.batch_size, shuffle=False, collate_fn=collate_fn)
    test_loader = torch.utils.data.DataLoader(ReviewDataset(X_test, y_test), batch_size=args.batch_size, shuffle=False, collate_fn=collate_fn)

    total_steps = len(train_loader) * args.epochs
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps)

    print(f"\n=== Training DistilBERT: {args.epochs} epoch(s), lr={args.learning_rate}, batch_size={args.batch_size} ===")
    start_time = time.time()
    best_val_acc, best_state = -1.0, None
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = run_epoch(model, train_loader, device, optimizer, scheduler)
        val_loss, val_acc = run_epoch(model, val_loader, device)
        print(f"Epoch {epoch}: train_loss={train_loss:.4f} train_acc={train_acc:.4f} val_loss={val_loss:.4f} val_acc={val_acc:.4f}")
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            import copy
            best_state = copy.deepcopy(model.state_dict())
    train_time = time.time() - start_time
    print(f"Trained in {train_time:.1f}s, best val_acc={best_val_acc:.4f}")

    if best_state is not None:
        model.load_state_dict(best_state)

    print("\n=== Evaluating on held-out TEST set ===")
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score, confusion_matrix, classification_report

    y_true, y_pred, y_prob = get_predictions(model, test_loader, device)
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred)),
        "recall": float(recall_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
    }
    print(metrics)
    cm = confusion_matrix(y_true, y_pred).tolist()
    print("Confusion matrix [[TN,FP],[FN,TP]]:", cm)
    print(classification_report(y_true, y_pred, target_names=["REAL", "FAKE"]))

    out_dir = PROJECT_ROOT / "models" / "fake_review_detector"
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"\nSaved fine-tuned checkpoint -> {out_dir}")

    write_json(PROJECT_ROOT / "results" / "fake_review_detector_training.json", {
        "base_checkpoint": BASE_CHECKPOINT,
        "dataset": "theArijitDas/Fake-Reviews-Dataset (HuggingFace Hub)",
        "dataset_size": len(df),
        "split_sizes": {"train": len(X_train), "val": len(X_val), "test": len(X_test)},
        "label_mapping": {"REAL": 0, "FAKE": 1},
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "batch_size": args.batch_size,
        "train_time_seconds": train_time,
        "best_val_accuracy": best_val_acc,
        "test_metrics": metrics,
        "confusion_matrix": cm,
        "seed": args.seed,
    })


if __name__ == "__main__":
    main()
