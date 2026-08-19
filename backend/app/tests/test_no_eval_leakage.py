"""Regression test for a real eval/train leakage bug (Technical Review #01):
retrain_bert_late_delivery_augmented.py's hand-crafted "held out" eval set
used to be templated from the exact same generator functions that built
training data, so several eval items were literal string matches against
the training set. assert_eval_is_held_out() now fails loudly if that happens
again -- this tests that guard directly, fast, without loading the full
Olist dataset."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend" / "scripts"))
from retrain_bert_late_delivery_augmented import NEGATION_EVAL_SET, assert_eval_is_held_out, build_synthetic_examples  # noqa: E402


def test_current_eval_set_is_held_out():
    """The actual shipped eval set must never overlap the actual shipped
    training templates -- this is the exact check that would have caught
    the original bug."""
    synthetic_df = build_synthetic_examples()
    real_train = pd.Series(["some unrelated real Olist review text"])
    assert_eval_is_held_out(synthetic_df, real_train, NEGATION_EVAL_SET)  # must not raise


def test_assert_eval_is_held_out_catches_literal_overlap():
    synthetic_df = pd.DataFrame({"text": ["the shipment coming late"], "label": [0]})
    real_train = pd.Series([])
    eval_set = [("the shipment coming late", 0), ("something else entirely", 1)]
    with pytest.raises(RuntimeError, match="Eval leakage"):
        assert_eval_is_held_out(synthetic_df, real_train, eval_set)


def test_assert_eval_is_held_out_is_case_and_whitespace_insensitive():
    """Leakage detection should catch near-duplicates, not just byte-identical strings."""
    synthetic_df = pd.DataFrame({"text": ["The Shipment  Coming Late"], "label": [0]})
    real_train = pd.Series([])
    eval_set = [("the shipment coming late", 0)]
    with pytest.raises(RuntimeError, match="Eval leakage"):
        assert_eval_is_held_out(synthetic_df, real_train, eval_set)


def test_assert_eval_is_held_out_passes_for_disjoint_sets():
    synthetic_df = pd.DataFrame({"text": ["completely different training sentence"], "label": [0]})
    real_train = pd.Series(["another unrelated training sentence"])
    eval_set = [("this eval sentence shares nothing with training", 0)]
    assert_eval_is_held_out(synthetic_df, real_train, eval_set)  # must not raise
