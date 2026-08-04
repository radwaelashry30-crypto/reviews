"""Sentiment-dataset construction, deduplication-before-split, and the CNN tokenizer.

Two dataset-construction paths are provided:

- `build_sentiment_dataframe(..., dedupe_before_split=False)` reproduces the
  notebook's ORIGINAL cell-117 behavior (split first, dedupe noticed after
  the fact in cell 120, dedupe applied to `bert_df` in cell 121 but the
  earlier `X_train`/`X_val`/`X_test` were never rebuilt from the deduplicated
  frame in the notebook — see DATA_LEAKAGE_AUDIT.md). Kept ONLY for
  "notebook reproduction mode" evaluation.

- `build_sentiment_dataframe(..., dedupe_before_split=True)` (the default,
  and the only mode `train.py`/`evaluate.py` use for "fair comparison" and
  "reproduced metrics") normalizes text, drops duplicate normalized text,
  resolves conflicting-label duplicates, and only THEN splits — eliminating
  the cross-split text leakage the notebook measured (1,097 duplicate texts
  shared across train/val/test).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from .utils import normalize_text_for_hash, stable_text_hash, write_json

LABEL_MAPPING = {"Negative": 0, "Positive": 1}
ID_TO_LABEL = {0: "Negative", 1: "Positive"}
NO_MESSAGE_SENTINEL = "No Message"


def normalize_review_text(text: str) -> str:
    """Normalize review text before duplicate detection (lowercase + collapsed whitespace)."""
    return normalize_text_for_hash(text)


def build_sentiment_dataframe(
    reviews: pd.DataFrame,
    text_column: str = "review_comment_message_en",
    raw_text_column: str = "review_comment_message",
    score_column: str = "review_score",
    review_id_column: str = "review_id",
) -> pd.DataFrame:
    """Binary sentiment frame: label 1-2 stars -> 0, 4-5 stars -> 1; drop 3-star and empty text.

    Matches notebook cell 117/121's filter exactly:
    `review_score in {1,2,4,5}`, `review_comment_message != "No Message"`,
    and a non-empty translated (`_en`) column.
    """
    mask = (
        reviews[score_column].isin([1, 2, 4, 5])
        & (reviews[raw_text_column] != NO_MESSAGE_SENTINEL)
        & (reviews[text_column].fillna("").astype(str).str.strip() != "")
    )
    out = reviews.loc[mask, [review_id_column, text_column, score_column]].copy()
    out["label"] = out[score_column].apply(lambda s: 0 if s in (1, 2) else 1)
    out = out.rename(columns={text_column: "text", review_id_column: "review_id"})
    out = out[["review_id", "text", "label"]].reset_index(drop=True)
    out["normalized_text"] = out["text"].map(normalize_review_text)
    out["text_hash"] = out["normalized_text"].map(lambda t: stable_text_hash(t))
    return out


@dataclass
class DeduplicationReport:
    rows_before: int
    rows_after: int
    duplicate_groups: int
    conflicting_label_groups: int
    conflicting_label_rows_dropped: int

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def resolve_conflicting_labels(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Drop text groups where the same normalized text carries both labels.

    A handful of near-identical short reviews (e.g. "ok", "bom") can appear
    with both a 1-2 star and a 4-5 star rating from different customers.
    Since these are unresolvable from text alone, and keeping either copy
    would inject a contradictory training signal, every row belonging to a
    conflicting-label group is dropped (not just one copy of it).
    Returns (frame, num_conflicting_groups, num_rows_dropped).
    """
    label_counts = df.groupby("normalized_text")["label"].nunique()
    conflicting_texts = set(label_counts[label_counts > 1].index)
    if not conflicting_texts:
        return df, 0, 0
    conflict_mask = df["normalized_text"].isin(conflicting_texts)
    dropped = int(conflict_mask.sum())
    return df.loc[~conflict_mask].reset_index(drop=True), len(conflicting_texts), dropped


def remove_duplicate_reviews(df: pd.DataFrame) -> tuple[pd.DataFrame, DeduplicationReport]:
    """Normalize text, resolve conflicting-label duplicates, then drop duplicate normalized text.

    This is the "clean before split" counterpart to the notebook's cell 121
    (`bert_df.drop_duplicates(subset=["text"])`), but operating on normalized
    text (case/whitespace-insensitive) rather than raw text, and explicitly
    handling conflicting labels first per the audit requirement.
    """
    rows_before = len(df)
    resolved, conflict_groups, conflict_dropped = resolve_conflicting_labels(df)
    duplicate_groups = int((resolved["normalized_text"].value_counts() > 1).sum())
    deduped = resolved.drop_duplicates(subset=["normalized_text"], keep="first").reset_index(drop=True)
    report = DeduplicationReport(
        rows_before=rows_before,
        rows_after=len(deduped),
        duplicate_groups=duplicate_groups,
        conflicting_label_groups=conflict_groups,
        conflicting_label_rows_dropped=conflict_dropped,
    )
    return deduped, report


@dataclass
class SplitResult:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame

    def overlap_report(self) -> dict:
        train_idx, val_idx, test_idx = set(self.train.index), set(self.val.index), set(self.test.index)
        train_txt = set(self.train["normalized_text"])
        val_txt = set(self.val["normalized_text"])
        test_txt = set(self.test["normalized_text"])
        train_raw = set(self.train["text"])
        val_raw = set(self.val["text"])
        test_raw = set(self.test["text"])
        return {
            "index_overlap": {
                "train_val": len(train_idx & val_idx),
                "train_test": len(train_idx & test_idx),
                "val_test": len(val_idx & test_idx),
            },
            "raw_text_overlap": {
                "train_val": len(train_raw & val_raw),
                "train_test": len(train_raw & test_raw),
                "val_test": len(val_raw & test_raw),
            },
            "normalized_text_overlap": {
                "train_val": len(train_txt & val_txt),
                "train_test": len(train_txt & test_txt),
                "val_test": len(val_txt & test_txt),
            },
            "sizes": {"train": len(self.train), "val": len(self.val), "test": len(self.test)},
        }


def split_sentiment_dataset(
    df: pd.DataFrame,
    seed: int = 42,
    test_size: float = 0.20,
    val_size_of_remainder: float = 0.125,
) -> SplitResult:
    """Stratified 70/10/20 train/val/test split — same proportions as the notebook (cell 119).

    Callers MUST pass an already-deduplicated `df` (see `remove_duplicate_reviews`)
    for the corrected/fair-comparison pipeline. `test_size=0.20` then
    `val_size_of_remainder=0.125` of the remaining 80% reproduces 70/10/20 exactly.
    """
    X_temp, X_test, y_temp, y_test = train_test_split(
        df, df["label"], test_size=test_size, random_state=seed, stratify=df["label"],
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=val_size_of_remainder, random_state=seed, stratify=y_temp,
    )
    # Deliberately NOT resetting each split's index here: `overlap_report()` below
    # compares original-dataframe row indices across splits to confirm sklearn's
    # train_test_split never reused a source row. Resetting every split's index
    # to start at 0 would make that check meaningless (every split would appear
    # to "overlap" positionally even though the underlying rows are disjoint).
    return SplitResult(train=X_train, val=X_val, test=X_test)


def save_split_manifest(
    split: SplitResult,
    path: str | Path,
    seed: int,
    dedupe_rule: str,
    source_dataset: str,
) -> None:
    """Persist stable identifiers for each split so evaluate.py/inference reuse the exact same rows."""
    payload = {
        "seed": seed,
        "dedupe_rule": dedupe_rule,
        "source_dataset": source_dataset,
        "split_ratio": {"train": 0.70, "val": 0.10, "test": 0.20},
        "label_mapping": LABEL_MAPPING,
        "sizes": {"train": len(split.train), "val": len(split.val), "test": len(split.test)},
        "splits": {
            name: frame[["review_id", "text_hash", "label"]].to_dict(orient="records")
            for name, frame in [("train", split.train), ("val", split.val), ("test", split.test)]
        },
    }
    write_json(path, payload, schema_version="1.0")


def load_split_manifest(path: str | Path) -> dict:
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CNN tokenizer — extracted verbatim from notebook cell 13 (SimpleVocabTokenizer)
# ---------------------------------------------------------------------------

DEFAULT_OOV_TOKEN = "<OOV>"


def simple_tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer. Notebook cell 13, unchanged."""
    return re.findall(r"\b\w+\b", str(text).lower())


class SimpleVocabTokenizer:
    """Frequency-capped word_index tokenizer (0=padding, 1=OOV). Notebook cell 13, unchanged.

    Must be fit ONLY on training text (see `train.py`); fitting on
    validation/test text would leak vocabulary frequency information across
    the split boundary.
    """

    def __init__(self, num_words: int, oov_token: str = DEFAULT_OOV_TOKEN):
        self.num_words = num_words
        self.oov_token = oov_token
        self.word_index: dict[str, int] = {oov_token: 1}

    def fit_on_texts(self, texts: Iterable[str]) -> None:
        counter: Counter = Counter()
        for text in texts:
            counter.update(simple_tokenize(text))
        for idx, (word, _) in enumerate(counter.most_common(self.num_words - 2), start=2):
            self.word_index[word] = idx

    def texts_to_sequences(self, texts: Iterable[str]) -> list[list[int]]:
        oov_idx = self.word_index[self.oov_token]
        return [[self.word_index.get(tok, oov_idx) for tok in simple_tokenize(text)] for text in texts]

    @property
    def vocab_size(self) -> int:
        return len(self.word_index)

    @property
    def max_index(self) -> int:
        return max(self.word_index.values()) if self.word_index else 0


def pad_sequences_np(sequences: list[list[int]], maxlen: int, padding: str = "post", truncating: str = "post") -> np.ndarray:
    """NumPy re-implementation of keras.preprocessing.sequence.pad_sequences. Notebook cell 13, unchanged."""
    arr = np.zeros((len(sequences), maxlen), dtype=np.int64)
    for i, seq in enumerate(sequences):
        if len(seq) > maxlen:
            seq = seq[:maxlen] if truncating == "post" else seq[-maxlen:]
        if padding == "post":
            arr[i, : len(seq)] = seq
        else:
            arr[i, -len(seq):] = seq
    return arr
