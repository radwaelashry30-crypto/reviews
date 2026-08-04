"""Model definitions and loaders for the two sentiment models.

CNN2DReviewSentiment is extracted verbatim from notebook cell 131 (verified:
loading `models/cnn2d_review_sentiment.pt` into this exact class with
`strict=True` succeeds, 3,049,345 trainable parameters, matching the
notebook's own printed parameter count).

BERT loading intentionally has NO fallback path. The original notebook's
inference cell (149) falls back to a freshly re-initialized
`LiYuan/amazon-review-sentiment-analysis` checkpoint with a random 2-class
head when loading the fine-tuned weights fails — silently producing
untrained predictions. `load_fine_tuned_bert` here raises instead.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import torch
import torch.nn as nn
import torch.nn.functional as F

BERT_BASE_CHECKPOINT = "LiYuan/amazon-review-sentiment-analysis"
CNN_MAX_WORDS = 30_000
CNN_MAX_LEN = 100
CNN_EMBEDDING_DIM = 100
CNN_FILTER_SIZES = (2, 3, 4, 5)
CNN_NUM_FILTERS = 32
CNN_DROPOUT = 0.5
CNN_PAD_IDX = 0
CNN_OOV_IDX = 1


class CNN2DReviewSentiment(nn.Module):
    """Multi-branch n-gram CNN2D: Embedding -> reshape to 2D -> parallel Conv2D
    branches (one per n-gram filter size) -> BatchNorm2d -> global max-pool ->
    concat -> Dense. Extracted verbatim from notebook cell 131."""

    def __init__(
        self,
        vocab_size: int = CNN_MAX_WORDS,
        max_len: int = CNN_MAX_LEN,
        embed_dim: int = CNN_EMBEDDING_DIM,
        num_filters: int = CNN_NUM_FILTERS,
        filter_sizes: tuple[int, ...] = CNN_FILTER_SIZES,
        dropout_rate: float = CNN_DROPOUT,
    ):
        super().__init__()
        self.embedding = nn.Embedding(num_embeddings=vocab_size, embedding_dim=embed_dim, padding_idx=CNN_PAD_IDX)
        self.embedding_dropout = nn.Dropout(0.2)

        self.branches = nn.ModuleList([
            nn.Sequential(
                nn.Conv2d(in_channels=1, out_channels=num_filters, kernel_size=(fs, embed_dim)),
                nn.BatchNorm2d(num_filters),
                nn.ReLU(),
            )
            for fs in filter_sizes
        ])

        self.dropout1 = nn.Dropout(dropout_rate)
        self.dense1 = nn.Linear(num_filters * len(filter_sizes), 32)
        self.dropout2 = nn.Dropout(dropout_rate)
        self.output_layer = nn.Linear(32, 1)  # raw logit; apply sigmoid at inference time

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.embedding(x)
        x = self.embedding_dropout(x)
        x = x.unsqueeze(1)

        branch_outputs = []
        for branch in self.branches:
            b = branch(x)
            b = F.adaptive_max_pool2d(b, output_size=1)
            branch_outputs.append(b.flatten(1))

        merged = torch.cat(branch_outputs, dim=1)
        out = self.dropout1(merged)
        out = F.relu(self.dense1(out))
        out = self.dropout2(out)
        return self.output_layer(out).squeeze(1)


def load_cnn2d_model(checkpoint_path: str | Path, device: torch.device | str = "cpu") -> CNN2DReviewSentiment:
    """Build CNN2DReviewSentiment and load the genuine checkpoint with strict=True.

    Raises RuntimeError (via strict=True) rather than silently ignoring
    mismatched or missing keys, per the "no silent strict=False" requirement.
    """
    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"CNN2D checkpoint not found at {checkpoint_path}")
    state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model = CNN2DReviewSentiment()
    model.load_state_dict(state_dict, strict=True)
    model.to(device)
    model.eval()
    return model


def create_bert_model(checkpoint: str = BERT_BASE_CHECKPOINT, num_labels: int = 2):
    """Load the base pretrained checkpoint and replace its head for binary classification.

    This is the TRAINING-time constructor (used by train.py before
    fine-tuning starts) — it intentionally reinitializes the classification
    head, matching notebook cell 126. It must never be used to serve
    predictions directly; use `load_fine_tuned_bert` for inference.
    """
    from transformers import AutoModelForSequenceClassification

    model = AutoModelForSequenceClassification.from_pretrained(
        checkpoint, num_labels=num_labels, ignore_mismatched_sizes=True,
    )
    model.config.id2label = {0: "Negative", 1: "Positive"}
    model.config.label2id = {"Negative": 0, "Positive": 1}
    return model


def load_fine_tuned_bert(model_dir: str | Path, device: torch.device | str = "cpu"):
    """Load the genuine fine-tuned BERT directory (config.json + weights + tokenizer).

    Fixes the notebook's inference-cell bugs (cell 149):
      1. Loads from the `save_pretrained()` directory, not a nonexistent
         `output/bert_sentiment_model.pt` raw-state-dict path.
      2. Returns the fine-tuned model/tokenizer explicitly rather than
         probing ambiguous `model`/`tokenizer` globals that could be shadowed
         by the Marian translation model/tokenizer loaded earlier in the notebook.
      3. NEVER falls back to a freshly initialized base checkpoint. If loading
         fails, this raises — it does not return untrained predictions.

    Returns (model, tokenizer).
    """
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_dir = Path(model_dir)
    required = ["config.json"]
    weight_files = ["model.safetensors", "pytorch_model.bin"]
    if not model_dir.is_dir() or not (model_dir / "config.json").is_file():
        raise FileNotFoundError(
            f"Fine-tuned BERT directory not found or incomplete at {model_dir}. "
            "Refusing to fall back to an untrained base checkpoint."
        )
    if not any((model_dir / w).is_file() for w in weight_files):
        raise FileNotFoundError(
            f"No model weights (model.safetensors or pytorch_model.bin) found in {model_dir}."
        )

    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

    if model.config.num_labels != 2:
        raise RuntimeError(
            f"Loaded BERT model has {model.config.num_labels} output labels, expected 2. "
            "This does not look like the fine-tuned sentiment classifier."
        )
    if dict(model.config.id2label) not in ({0: "Negative", 1: "Positive"}, {"0": "Negative", "1": "Positive"}):
        # transformers may load id2label keys as either int or str depending on version
        id2label_normalized = {int(k): v for k, v in model.config.id2label.items()}
        if id2label_normalized != {0: "Negative", 1: "Positive"}:
            raise RuntimeError(f"Unexpected id2label mapping on loaded BERT model: {model.config.id2label}")

    model.to(device)
    model.eval()
    return model, tokenizer


ModelName = Literal["bert", "cnn2d"]


def get_model(
    model_name: ModelName,
    *,
    bert_model_dir: str | Path | None = None,
    cnn_checkpoint_path: str | Path | None = None,
    device: torch.device | str = "cpu",
):
    """Single entry point used by services/tests to load either model by name."""
    if model_name == "bert":
        if bert_model_dir is None:
            raise ValueError("bert_model_dir is required for model_name='bert'")
        return load_fine_tuned_bert(bert_model_dir, device=device)
    if model_name == "cnn2d":
        if cnn_checkpoint_path is None:
            raise ValueError("cnn_checkpoint_path is required for model_name='cnn2d'")
        return load_cnn2d_model(cnn_checkpoint_path, device=device)
    raise ValueError(f"Unknown model_name: {model_name!r}. Expected 'bert' or 'cnn2d'.")
