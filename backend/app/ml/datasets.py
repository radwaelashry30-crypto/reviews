"""PyTorch Dataset/DataLoader construction for BERT and CNN2D.

Extracted from notebook cell 12 (`ReviewSentimentDataset`, `make_collate_fn`)
and cells 129/133 (CNN tensor loaders).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset, TensorDataset

from .preprocessing import SimpleVocabTokenizer, pad_sequences_np


class ReviewSentimentDataset(Dataset):
    """Holds raw text/label pairs; tokenization happens lazily in the collate
    function so each batch is padded only to its own longest sequence
    (dynamic padding). Notebook cell 12, unchanged."""

    def __init__(self, texts, labels):
        self.texts = list(texts)
        self.labels = list(labels)

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx):
        return self.texts[idx], int(self.labels[idx])


def make_bert_collate_fn(tokenizer, max_len: int):
    """Dynamic-padding collate function for BERT DataLoaders. Notebook cell 12."""

    def collate_fn(batch):
        texts, labels = zip(*batch)
        encodings = tokenizer(
            list(texts), max_length=max_len, padding=True, truncation=True, return_tensors="pt",
        )
        encodings["labels"] = torch.tensor(labels, dtype=torch.long)
        return encodings

    return collate_fn


def build_bert_dataloader(texts, labels, tokenizer, max_len: int, batch_size: int, shuffle: bool) -> DataLoader:
    dataset = ReviewSentimentDataset(texts, labels)
    collate_fn = make_bert_collate_fn(tokenizer, max_len)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, collate_fn=collate_fn)


def encode_texts_for_cnn(texts, tokenizer: SimpleVocabTokenizer, max_len: int) -> np.ndarray:
    """Text -> integer sequence -> post-padded/post-truncated array. Notebook cell 129."""
    seqs = tokenizer.texts_to_sequences(texts)
    return pad_sequences_np(seqs, maxlen=max_len, padding="post", truncating="post")


def build_cnn_dataloader(X_seq: np.ndarray, y, batch_size: int, shuffle: bool) -> DataLoader:
    """Tensor DataLoader for CNN2D. Notebook cell 14 (`to_tensor_loader`)."""
    y_values = y.values if hasattr(y, "values") else y
    dataset = TensorDataset(
        torch.tensor(X_seq, dtype=torch.long),
        torch.tensor(y_values, dtype=torch.float32),
    )
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)
