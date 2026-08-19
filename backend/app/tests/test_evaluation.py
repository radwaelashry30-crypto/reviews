"""Tests for app/ml/evaluation.py -- previously zero test coverage for the
metric-computation module every published number in this project (README,
results/*.json, MODEL_CARD.md) ultimately traces back to (Technical Review #21).
Pure functions over numpy arrays -- no model loading needed."""
import numpy as np

from app.ml.evaluation import classification_report_dict, confusion_matrix_dict, evaluate_classification


def test_evaluate_classification_perfect_predictions():
    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_pred = np.array([0, 0, 1, 1, 0, 1])
    y_prob = np.array([0.1, 0.05, 0.9, 0.95, 0.2, 0.8])
    m = evaluate_classification(y_true, y_pred, y_prob)
    assert m.accuracy == 1.0
    assert m.f1_macro == 1.0
    assert m.roc_auc == 1.0
    assert m.mcc == 1.0
    assert m.n_samples == 6


def test_evaluate_classification_known_confusion_matrix():
    # 2 TN, 1 FP, 1 FN, 4 TP -- hand-computable accuracy = 6/8
    y_true = np.array([0, 0, 0, 1, 1, 1, 1, 1])
    y_pred = np.array([0, 0, 1, 0, 1, 1, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.6, 0.4, 0.7, 0.8, 0.9, 0.6])
    m = evaluate_classification(y_true, y_pred, y_prob)
    assert m.accuracy == 6 / 8

    cm = confusion_matrix_dict(y_true, y_pred)
    assert cm["true_negative"] == 2
    assert cm["false_positive"] == 1
    assert cm["false_negative"] == 1
    assert cm["true_positive"] == 4
    assert sum(sum(row) for row in cm["matrix"]) == 8


def test_evaluate_classification_worst_case_mcc_near_zero_for_random():
    """A model that ignores the input entirely (always predicts the majority
    class) should score MCC near 0, not a misleadingly high accuracy alone --
    this is exactly why MCC is in the required metric suite."""
    y_true = np.array([1] * 9 + [0] * 1)
    y_pred = np.array([1] * 10)  # always predicts positive, ignores input
    y_prob = np.array([0.9] * 10)
    m = evaluate_classification(y_true, y_pred, y_prob)
    assert m.accuracy == 0.9  # looks great on accuracy alone
    assert m.mcc == 0.0  # but MCC correctly shows zero real skill


def test_classification_report_dict_has_expected_keys():
    y_true = np.array([0, 1, 0, 1])
    y_pred = np.array([0, 1, 1, 1])
    report = classification_report_dict(y_true, y_pred)
    assert "Negative" in report
    assert "Positive" in report
    assert "accuracy" in report
    assert "macro avg" in report


def test_confusion_matrix_dict_labels_match_class_names():
    y_true = np.array([0, 1])
    y_pred = np.array([0, 1])
    cm = confusion_matrix_dict(y_true, y_pred)
    assert cm["labels"] == ["Negative", "Positive"]
