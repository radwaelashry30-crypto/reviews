#!/usr/bin/env python
"""Fine-tunes a DistilBERT fake-review detector on the Ott et al. Deceptive
Opinion Spam Corpus, WITH paraphrase-consistency training -- the one thing
NOT tried in the previous two attempts (see below).

Why this exists / what's different this time
----------------------------------------------
Two previous checkpoints failed `scripts/paraphrase_stability_test.py`:
  1. `jb10231/fake-review-detector` (external, unknown training data).
  2. `models/fake_review_detector` (this project's own retrain on
     theArijitDas/Fake-Reviews-Dataset -- 97% held-out test accuracy, but
     STILL flipped verdicts under meaning-preserving synonym substitution;
     see app/ml/fake_review_detection.py's module docstring).

Both prior attempts trained with plain cross-entropy only -- nothing in the
objective ever told the model that two differently-worded sentences with the
same meaning should get the same verdict. This script adds that directly:
for a fraction of each training batch, a WordNet-paraphrased version of the
same review is also scored, and a consistency loss (KL divergence between
the original's and the paraphrase's output distributions) is added to the
standard classification loss. This is the first attempt where "be stable
under paraphrasing" is actually part of what the model is optimized for,
rather than something we only measure after the fact.

Second key difference: the LABEL is different. theArijitDas's dataset labels
AI-generated (GPT-2) vs human-written text -- a text-origin task. This
corpus labels genuinely deceptive (crowdworker instructed to write a
convincing fake review) vs truthful (real guest, verified source) -- a
deceptive-intent task, which is what "fake review" actually means in this
project's context. Not a redundant repeat of the first failed attempt.

Dataset: Ott et al. 2011/2013 (Cornell, ACL/NAACL, peer-reviewed), via
Kaggle mirror rtatman/deceptive-opinion-spam-corpus. 1,600 hotel reviews:
800 truthful (400 TripAdvisor + 400 other travel sites) + 800 deceptive
(400 positive + 400 negative, all Mechanical Turk). Balanced against BOTH
label and sentiment polarity (400/400/400/400) -- unlike the Amazon
"spam/non-spam" dataset first considered for this, which turned out to
just be a 1:1 proxy for star rating (every 4-5* review labeled "spam",
every 1-3* review labeled "not spam", 0% overlap -- verified directly on
the downloaded data and confirmed by other users on Kaggle's discussion
tab). That dataset was rejected before any training was attempted.

Honest scoping, unchanged from the previous attempt: hotel domain, not
Olist e-commerce -- a domain-shift caveat applies regardless of outcome.

Usage:
    python scripts/train_fake_review_detector_v2_consistency.py --epochs 4
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ml.utils import get_device, set_seed, write_json  # noqa: E402

BASE_CHECKPOINT = "distilbert-base-uncased"
MAX_LEN = 256
SRC_CSV = PROJECT_ROOT / "data" / "external" / "deceptive_opinion_spam" / "deceptive-opinion.csv"
LABEL_MAPPING = {"truthful": 0, "deceptive": 1}


# --------------------------------------------------------------------------- #
# Data loading + leak-free split (same discipline as DATA_LEAKAGE_AUDIT.md:
# normalize text, drop duplicates, THEN split -- never the other way round)
# --------------------------------------------------------------------------- #

def normalize_text(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def load_and_clean() -> pd.DataFrame:
    df = pd.read_csv(SRC_CSV)
    df["text"] = df["text"].astype(str).str.strip()
    df["norm_text"] = df["text"].apply(normalize_text)
    before = len(df)
    df = df.drop_duplicates(subset=["norm_text"]).reset_index(drop=True)
    print(f"Rows: {before} -> {len(df)} after de-duplication")
    df["label"] = df["deceptive"].map(LABEL_MAPPING)
    assert df["label"].isna().sum() == 0
    return df


def split_dataset(df: pd.DataFrame, seed: int):
    from sklearn.model_selection import train_test_split

    train_df, temp_df = train_test_split(df, test_size=0.30, random_state=seed, stratify=df[["label", "polarity"]])
    val_df, test_df = train_test_split(temp_df, test_size=2 / 3, random_state=seed, stratify=temp_df[["label", "polarity"]])

    train_texts = set(train_df["norm_text"])
    val_texts = set(val_df["norm_text"])
    test_texts = set(test_df["norm_text"])
    assert not (train_texts & val_texts), "train/val text overlap"
    assert not (train_texts & test_texts), "train/test text overlap"
    assert not (val_texts & test_texts), "val/test text overlap"
    print(f"Split -- train: {len(train_df)}  val: {len(val_df)}  test: {len(test_df)}  (verified: zero text overlap)")
    return train_df, val_df, test_df


# --------------------------------------------------------------------------- #
# Paraphrase generation for consistency training (same WordNet-substitution
# technique as app/ml/fake_review_detection.py's _wordnet_variant, reused
# here so the training-time probe matches the eval-time probe)
# --------------------------------------------------------------------------- #

def wordnet_paraphrase(text: str, max_swaps: int = 4) -> str | None:
    from nltk.corpus import wordnet as wn

    words = text.split()
    new_words, swapped = [], 0
    for word in words:
        core = re.sub(r"[^a-zA-Z]", "", word)
        replacement = None
        if swapped < max_swaps and len(core) > 3:
            for syn in wn.synsets(core.lower()):
                for lemma in syn.lemmas():
                    name = lemma.name()
                    if "_" not in name and name.lower() != core.lower():
                        replacement = name
                        break
                if replacement:
                    break
        if replacement:
            new_words.append(word.replace(core, replacement, 1))
            swapped += 1
        else:
            new_words.append(word)
    return " ".join(new_words) if swapped else None


_NEUTRAL_FILLERS = [
    ", overall.",
    " I ordered this a little while ago.",
    ", and that's about it.",
    " It came in normal packaging.",
    " Just wanted to share my thoughts.",
    " Wrote this after using it for a bit.",
    ", for what it's worth.",
    " That's my honest take on it.",
    " I figured I'd leave a review.",
    " Hope this helps someone deciding.",
]


def append_neutral_filler(text: str, seed_val: int) -> str:
    """Appends a short, meaning-irrelevant clause. The first stability run
    (consistency_weight=1.0 and 4.0, WordNet-paraphrase pairs only) fixed
    synonym-substitution instability (0/6 flips) but LEFT length-sensitivity
    unfixed (spread actually got slightly worse: 0.22 -> 0.29) -- the
    consistency loss only ever saw same-length paraphrases, so it had no
    signal telling it that appending neutral filler shouldn't move the
    verdict either. This targets that specific, now-diagnosed gap."""
    filler = _NEUTRAL_FILLERS[seed_val % len(_NEUTRAL_FILLERS)]
    return text.rstrip(". ") + filler


def build_paraphrase_column(df: pd.DataFrame) -> pd.DataFrame:
    """Each row's consistency partner combines BOTH transformations this
    project has directly measured as breaking these models: a WordNet
    synonym substitution (meaning-preserving, tests lexical-choice
    sensitivity) AND an appended neutral filler clause (meaning-preserving,
    tests length sensitivity). Training against only one type left the other
    unfixed (see append_neutral_filler's docstring); combining them makes
    both part of the same consistency signal."""
    df = df.copy()
    paraphrases = []
    n_generated = 0
    for i, text in enumerate(df["text"]):
        p = wordnet_paraphrase(text)
        if p is None:
            p = text
        else:
            n_generated += 1
        p = append_neutral_filler(p, i)
        paraphrases.append(p)
    df["paraphrase"] = paraphrases
    print(f"Generated {n_generated}/{len(df)} genuine WordNet paraphrases (all also filler-extended) for consistency training")
    return df


# --------------------------------------------------------------------------- #
# Dataset / collation
# --------------------------------------------------------------------------- #

class ConsistencyDataset(torch.utils.data.Dataset):
    """Each item carries the original text, its label, AND a paraphrase of
    the same text -- both get tokenized and scored every step."""

    def __init__(self, texts, paraphrases, labels):
        self.texts = list(texts)
        self.paraphrases = list(paraphrases)
        self.labels = list(labels)

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return self.texts[idx], self.paraphrases[idx], int(self.labels[idx])


def make_collate_fn(tokenizer, max_len: int, with_paraphrase: bool):
    def collate(batch):
        if with_paraphrase:
            texts, paraphrases, labels = zip(*batch)
            enc = tokenizer(list(texts), max_length=max_len, padding=True, truncation=True, return_tensors="pt")
            enc_p = tokenizer(list(paraphrases), max_length=max_len, padding=True, truncation=True, return_tensors="pt")
            enc["labels"] = torch.tensor(labels, dtype=torch.long)
            return enc, enc_p
        texts, _, labels = zip(*batch)
        enc = tokenizer(list(texts), max_length=max_len, padding=True, truncation=True, return_tensors="pt")
        enc["labels"] = torch.tensor(labels, dtype=torch.long)
        return enc, None
    return collate


# --------------------------------------------------------------------------- #
# Training with a consistency loss term
# --------------------------------------------------------------------------- #

def run_train_epoch(model, loader, device, optimizer, scheduler, consistency_weight: float):
    model.train()
    total_ce, total_consistency, correct, total = 0.0, 0.0, 0, 0
    for enc, enc_p in loader:
        enc = {k: v.to(device) for k, v in enc.items()}
        labels = enc["labels"]
        outputs = model(**enc)
        ce_loss = outputs.loss

        consistency_loss = torch.tensor(0.0, device=device)
        if enc_p is not None:
            enc_p = {k: v.to(device) for k, v in enc_p.items()}
            logits_p = model(input_ids=enc_p["input_ids"], attention_mask=enc_p["attention_mask"]).logits
            log_probs_orig = F.log_softmax(outputs.logits, dim=1)
            probs_paraphrase = F.softmax(logits_p, dim=1)
            # KL(paraphrase || original), symmetrized by also computing the
            # reverse direction -- penalizes the model whichever way its two
            # views of the "same" review disagree.
            log_probs_p = F.log_softmax(logits_p, dim=1)
            probs_orig = F.softmax(outputs.logits, dim=1)
            kl_1 = F.kl_div(log_probs_orig, probs_paraphrase, reduction="batchmean")
            kl_2 = F.kl_div(log_probs_p, probs_orig, reduction="batchmean")
            consistency_loss = (kl_1 + kl_2) / 2

        loss = ce_loss + consistency_weight * consistency_loss

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        preds = torch.argmax(outputs.logits, dim=1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)
        total_ce += ce_loss.item() * labels.size(0)
        total_consistency += float(consistency_loss.item()) * labels.size(0)
    return total_ce / total, total_consistency / total, correct / total


@torch.no_grad()
def run_eval_epoch(model, loader, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    for enc, _ in loader:
        enc = {k: v.to(device) for k, v in enc.items()}
        labels = enc["labels"]
        outputs = model(**enc)
        preds = torch.argmax(outputs.logits, dim=1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)
        total_loss += outputs.loss.item() * labels.size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def get_predictions(model, loader, device):
    model.eval()
    all_labels, all_preds, all_probs = [], [], []
    for enc, _ in loader:
        labels = enc["labels"]
        inputs = {k: v.to(device) for k, v in enc.items() if k != "labels"}
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=1)[:, 1]
        preds = torch.argmax(logits, dim=1)
        all_labels.append(labels.numpy())
        all_preds.append(preds.cpu().numpy())
        all_probs.append(probs.cpu().numpy())
    return np.concatenate(all_labels), np.concatenate(all_preds), np.concatenate(all_probs)


def wilson_confint(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z ** 2 / n
    center = phat + z ** 2 / (2 * n)
    margin = z * ((phat * (1 - phat) / n + z ** 2 / (4 * n ** 2)) ** 0.5)
    return ((center - margin) / denom, (center + margin) / denom)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--consistency-weight", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    device = get_device()
    print(f"Device: {device}")

    print("=== Loading Ott et al. Deceptive Opinion Spam Corpus ===")
    df = load_and_clean()
    print(f"Label balance: {df['label'].value_counts(normalize=True).to_dict()}")

    train_df, val_df, test_df = split_dataset(df, args.seed)
    train_df = build_paraphrase_column(train_df)

    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

    tokenizer = AutoTokenizer.from_pretrained(BASE_CHECKPOINT)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_CHECKPOINT, num_labels=2)
    model.config.id2label = {0: "REAL", 1: "FAKE"}
    model.config.label2id = {"REAL": 0, "FAKE": 1}
    model.to(device)

    train_collate = make_collate_fn(tokenizer, MAX_LEN, with_paraphrase=True)
    eval_collate = make_collate_fn(tokenizer, MAX_LEN, with_paraphrase=False)

    train_ds = ConsistencyDataset(train_df["text"], train_df["paraphrase"], train_df["label"])
    val_ds = ConsistencyDataset(val_df["text"], val_df["text"], val_df["label"])
    test_ds = ConsistencyDataset(test_df["text"], test_df["text"], test_df["label"])

    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=train_collate)
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=eval_collate)
    test_loader = torch.utils.data.DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, collate_fn=eval_collate)

    total_steps = len(train_loader) * args.epochs
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps)

    print(f"\n=== Training DistilBERT + consistency loss (weight={args.consistency_weight}): "
          f"{args.epochs} epoch(s), lr={args.learning_rate}, batch_size={args.batch_size} ===")
    start_time = time.time()
    best_val_acc, best_state = -1.0, None
    for epoch in range(1, args.epochs + 1):
        ce, cons, train_acc = run_train_epoch(model, train_loader, device, optimizer, scheduler, args.consistency_weight)
        val_loss, val_acc = run_eval_epoch(model, val_loader, device)
        print(f"Epoch {epoch}: ce_loss={ce:.4f} consistency_loss={cons:.4f} train_acc={train_acc:.4f} "
              f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}")
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = copy.deepcopy(model.state_dict())
    train_time = time.time() - start_time
    print(f"Trained in {train_time:.1f}s, best val_acc={best_val_acc:.4f}")

    if best_state is not None:
        model.load_state_dict(best_state)

    print("\n=== Evaluating on held-out TEST set ===")
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score, confusion_matrix, classification_report

    y_true, y_pred, y_prob = get_predictions(model, test_loader, device)
    n_correct = int((y_true == y_pred).sum())
    acc_ci = wilson_confint(n_correct, len(y_true))
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "accuracy_95ci": acc_ci,
        "precision": float(precision_score(y_true, y_pred)),
        "recall": float(recall_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "n_test": int(len(y_true)),
    }
    print(metrics)
    cm = confusion_matrix(y_true, y_pred).tolist()
    print("Confusion matrix [[TN,FP],[FN,TP]]:", cm)
    print(classification_report(y_true, y_pred, target_names=["REAL", "FAKE"]))

    out_dir = PROJECT_ROOT / "models" / "fake_review_detector_v2_consistency"
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"\nSaved fine-tuned checkpoint -> {out_dir}")

    write_json(PROJECT_ROOT / "results" / "fake_review_detector_v2_consistency_training.json", {
        "base_checkpoint": BASE_CHECKPOINT,
        "dataset": "Ott et al. Deceptive Opinion Spam Corpus (Cornell, ACL 2011 / NAACL 2013), via Kaggle rtatman/deceptive-opinion-spam-corpus",
        "dataset_size": len(df),
        "split_sizes": {"train": len(train_df), "val": len(val_df), "test": len(test_df)},
        "label_mapping": {"REAL": 0, "FAKE": 1},
        "training_method": "cross-entropy + symmetric KL-divergence consistency loss against a WordNet-paraphrased view of each training review",
        "consistency_weight": args.consistency_weight,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "batch_size": args.batch_size,
        "train_time_seconds": train_time,
        "best_val_accuracy": best_val_acc,
        "test_metrics": metrics,
        "confusion_matrix": cm,
        "seed": args.seed,
        "domain_shift_caveat": "Trained on hotel reviews (Chicago hotels); applied in this app to Olist e-commerce reviews. Not the same domain.",
    })


if __name__ == "__main__":
    main()
