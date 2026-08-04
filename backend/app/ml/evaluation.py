"""Shared evaluation helpers for BERT and CNN2D. Extracted from notebook cells 15, 136, 138.

Softmax (BERT) and sigmoid (CNN2D) are each applied exactly once, inside
these functions only — callers must not re-apply either.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score, average_precision_score, classification_report,
    confusion_matrix, f1_score, matthews_corrcoef, precision_score,
    recall_score, roc_auc_score,
)

CLASS_NAMES = ("Negative", "Positive")


@torch.no_grad()
def get_bert_predictions(model, loader) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Runs inference over a DataLoader; returns (y_true, y_pred, y_prob_positive_class).

    Uses model.eval() + torch.no_grad(); applies softmax exactly once.
    """
    model.eval()
    device = next(model.parameters()).device
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


@torch.no_grad()
def get_cnn_predictions(model, loader) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Runs inference over a DataLoader; returns (y_true, y_pred, y_prob_positive_class).

    Uses model.eval() + torch.no_grad(); applies sigmoid exactly once.
    """
    model.eval()
    device = next(model.parameters()).device
    all_labels, all_preds, all_probs = [], [], []
    for X_batch, y_batch in loader:
        logits = model(X_batch.to(device))
        probs = torch.sigmoid(logits).cpu().numpy()
        preds = (probs >= 0.5).astype(int)
        all_labels.append(y_batch.numpy())
        all_preds.append(preds)
        all_probs.append(probs)
    return np.concatenate(all_labels).astype(int), np.concatenate(all_preds), np.concatenate(all_probs)


@dataclass
class ClassificationMetrics:
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    roc_auc: float
    pr_auc: float
    mcc: float
    loss: float | None = None
    n_samples: int = 0

    def to_dict(self) -> dict:
        return {
            "accuracy": self.accuracy,
            "precision_macro": self.precision_macro,
            "recall_macro": self.recall_macro,
            "f1_macro": self.f1_macro,
            "roc_auc": self.roc_auc,
            "pr_auc": self.pr_auc,
            "mcc": self.mcc,
            "loss": self.loss,
            "n_samples": self.n_samples,
        }


def evaluate_classification(y_true, y_pred, y_prob, loss: float | None = None) -> ClassificationMetrics:
    """Full required metric suite: Accuracy, macro P/R/F1, ROC-AUC, PR-AUC, MCC. Notebook cell 15."""
    return ClassificationMetrics(
        accuracy=float(accuracy_score(y_true, y_pred)),
        precision_macro=float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        recall_macro=float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        f1_macro=float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        roc_auc=float(roc_auc_score(y_true, y_prob)),
        pr_auc=float(average_precision_score(y_true, y_prob)),
        mcc=float(matthews_corrcoef(y_true, y_pred)),
        loss=loss,
        n_samples=int(len(y_true)),
    )


def classification_report_dict(y_true, y_pred, class_names: tuple[str, str] = CLASS_NAMES) -> dict:
    return classification_report(y_true, y_pred, target_names=list(class_names), output_dict=True, zero_division=0)


def confusion_matrix_dict(y_true, y_pred, class_names: tuple[str, str] = CLASS_NAMES) -> dict:
    cm = confusion_matrix(y_true, y_pred)
    return {
        "labels": list(class_names),
        "matrix": cm.tolist(),
        "true_negative": int(cm[0, 0]), "false_positive": int(cm[0, 1]),
        "false_negative": int(cm[1, 0]), "true_positive": int(cm[1, 1]),
    }
