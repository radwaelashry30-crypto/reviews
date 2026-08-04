"""Training loops for BERT and CNN2D. Extracted from notebook cells 14, 126, 133.

Not imported by the API — training only happens via `train.py`, never from a
request handler, per the "no training during inference / no training through
a public API endpoint" requirement.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field

import torch
import torch.nn as nn

BERT_EPOCHS = 3
BERT_LEARNING_RATE = 2e-5
BERT_WEIGHT_DECAY = 0.01
BERT_EARLY_STOPPING_PATIENCE = 2
BERT_WARMUP_RATIO = 0.10
BERT_MAX_GRAD_NORM = 1.0

CNN_EPOCHS = 10
CNN_LR = 1e-3
CNN_L2_REG = 1e-3
CNN_LABEL_SMOOTHING = 0.1
CNN_EARLY_STOPPING_PATIENCE = 3
CNN_LR_PATIENCE = 2
CNN_LR_FACTOR = 0.5
CNN_MIN_LR = 1e-6


def run_bert_epoch(model, loader, device, optimizer=None, scheduler=None) -> tuple[float, float]:
    """One pass over `loader`. Trains if `optimizer` is given, else evaluates. Notebook cell 14."""
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
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=BERT_MAX_GRAD_NORM)
                optimizer.step()
                scheduler.step()

            preds = torch.argmax(outputs.logits, dim=1)
            correct += (preds == batch["labels"]).sum().item()
            total += batch["labels"].size(0)
            total_loss += loss.item() * batch["labels"].size(0)

    return total_loss / total, correct / total


def smooth_labels(y: torch.Tensor, smoothing: float = CNN_LABEL_SMOOTHING) -> torch.Tensor:
    return y * (1.0 - smoothing) + 0.5 * smoothing


def run_cnn_epoch(model, loader, criterion, device, optimizer=None) -> tuple[float, float]:
    """One pass over `loader` for CNN2D. Notebook cell 14."""
    is_train = optimizer is not None
    model.train() if is_train else model.eval()

    total_loss, correct, total = 0.0, 0, 0
    with torch.set_grad_enabled(is_train):
        for X_batch, y_batch in loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            logits = model(X_batch)
            loss = criterion(logits, smooth_labels(y_batch))

            if is_train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            preds = (torch.sigmoid(logits) >= 0.5).float()
            correct += (preds == y_batch).sum().item()
            total += y_batch.size(0)
            total_loss += loss.item() * y_batch.size(0)

    return total_loss / total, correct / total


@dataclass
class TrainingHistory:
    loss: list[float] = field(default_factory=list)
    accuracy: list[float] = field(default_factory=list)
    val_loss: list[float] = field(default_factory=list)
    val_accuracy: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"loss": self.loss, "accuracy": self.accuracy, "val_loss": self.val_loss, "val_accuracy": self.val_accuracy}


def train_bert(
    model, train_loader, val_loader, device,
    epochs: int = BERT_EPOCHS, lr: float = BERT_LEARNING_RATE, weight_decay: float = BERT_WEIGHT_DECAY,
    early_stopping_patience: int = BERT_EARLY_STOPPING_PATIENCE, checkpoint_dir: str | None = None,
) -> tuple[dict, TrainingHistory, float, int]:
    """Fine-tunes `model` in place. Returns (best_state_dict, history, train_time_seconds, best_epoch).

    AdamW + linear warmup/decay schedule (10% warmup), gradient clipping at
    max_norm=1.0, early stopping on validation accuracy. Notebook cell 126.
    """
    from pathlib import Path
    from transformers import get_linear_schedule_with_warmup

    total_train_steps = len(train_loader) * epochs
    warmup_steps = int(BERT_WARMUP_RATIO * total_train_steps)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_train_steps)

    if checkpoint_dir:
        Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)

    history = TrainingHistory()
    best_val_acc = -1.0
    best_state_dict = None
    best_epoch = 0
    epochs_without_improvement = 0
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        train_loss, train_acc = run_bert_epoch(model, train_loader, device, optimizer, scheduler)
        val_loss, val_acc = run_bert_epoch(model, val_loader, device)

        history.loss.append(train_loss)
        history.accuracy.append(train_acc)
        history.val_loss.append(val_loss)
        history.val_accuracy.append(val_acc)

        if checkpoint_dir:
            torch.save(model.state_dict(), Path(checkpoint_dir) / f"bert_review_sentiment_epoch_{epoch:02d}.pt")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state_dict = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= early_stopping_patience:
                break

    train_time = time.time() - start_time
    return best_state_dict, history, train_time, best_epoch


def train_cnn2d(
    model, train_loader, val_loader, device, class_weights_tensor: torch.Tensor,
    epochs: int = CNN_EPOCHS, lr: float = CNN_LR, weight_decay: float = CNN_L2_REG,
    early_stopping_patience: int = CNN_EARLY_STOPPING_PATIENCE,
) -> tuple[dict, TrainingHistory, float, int]:
    """Trains CNN2DReviewSentiment in place. Returns (best_state_dict, history, train_time_seconds, best_epoch).

    Adam optimizer, ReduceLROnPlateau on val_loss, BCEWithLogitsLoss with
    class-balanced pos_weight, label smoothing, early stopping on val_loss.
    Notebook cell 133.
    """
    pos_weight = (class_weights_tensor[1] / class_weights_tensor[0]).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=CNN_LR_FACTOR, patience=CNN_LR_PATIENCE, min_lr=CNN_MIN_LR,
    )

    history = TrainingHistory()
    best_val_loss = float("inf")
    best_state_dict = None
    best_epoch = 0
    epochs_without_improvement = 0
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        train_loss, train_acc = run_cnn_epoch(model, train_loader, criterion, device, optimizer)
        val_loss, val_acc = run_cnn_epoch(model, val_loader, criterion, device)
        scheduler.step(val_loss)

        history.loss.append(train_loss)
        history.accuracy.append(train_acc)
        history.val_loss.append(val_loss)
        history.val_accuracy.append(val_acc)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state_dict = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= early_stopping_patience:
                break

    train_time = time.time() - start_time
    return best_state_dict, history, train_time, best_epoch
