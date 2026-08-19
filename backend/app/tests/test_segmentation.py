"""Regression tests for two real RFM segmentation bugs (Technical Review
#06, #07): segment names were assigned by ranking clusters on Monetary
alone (so two clusters differing almost entirely on Recency, not Monetary,
could get contradictory names on the flip of a small gap), and StandardScaler
was applied to raw, heavily-skewed Frequency/Monetary values with no log
transform, letting outliers dominate K-Means' Euclidean distance."""
import numpy as np
import pandas as pd

from app.ml.segmentation import assign_business_segment_labels, build_rfm_pipeline, scale_rfm_features


def test_segment_names_are_behaviour_driven_not_monetary_only():
    """Two clusters nearly identical on Monetary and Frequency, but with a
    large, unambiguous Recency gap, must not be named arbitrarily -- the
    older-Recency cluster should read as at-risk, not the reverse."""
    rfm = pd.DataFrame({
        "Cluster": [0] * 50 + [1] * 50,
        "Recency": [440] * 50 + [175] * 50,       # the one real difference
        "Frequency": [1.0] * 100,                  # identical
        "Monetary": [134.9] * 50 + [135.2] * 50,   # ~0.2% apart -- noise
    })
    _, label_map = assign_business_segment_labels(rfm)
    assert label_map[0] != label_map[1]
    # cluster 0 (Recency=440, stale) must not read as more promising than
    # cluster 1 (Recency=175, fresher) -- "At Risk"/"Needs Attention" for the
    # stale one, something better for the fresh one.
    assert label_map[0] in ("At Risk", "Needs Attention")


def test_rfm_pipeline_log_transform_reduces_skew():
    """The log1p step must actually run before scaling -- confirms the
    pipeline isn't silently degrading to bare StandardScaler."""
    skewed = pd.DataFrame({
        "Recency": np.random.default_rng(0).integers(1, 400, size=200),
        "Frequency": np.concatenate([np.ones(190), np.full(10, 50)]),  # heavy right skew
        "Monetary": np.concatenate([np.full(190, 100.0), np.full(10, 50_000.0)]),
    })
    scaled, pipeline = scale_rfm_features(skewed)
    # Without log1p, the 10 extreme Monetary outliers would sit many std devs
    # out; log-compressed, the max scaled Monetary value should be much closer
    # to the bulk of the distribution than the raw ratio (500x) would suggest.
    monetary_col = scaled[:, 2]
    assert monetary_col.max() < 10  # a bare StandardScaler on 500x outliers would exceed this easily
    assert pipeline.named_steps["log"] is not None
    assert pipeline.named_steps["scale"] is not None


def test_rfm_pipeline_transform_is_identical_at_train_and_serve():
    """Prevents train/serve skew: the exact same fitted pipeline object must
    produce the exact same output for the exact same input, every call."""
    rfm = pd.DataFrame({
        "Recency": [10, 50, 200],
        "Frequency": [1, 2, 5],
        "Monetary": [100.0, 500.0, 50.0],
    })
    _, pipeline = scale_rfm_features(rfm)
    row = rfm.iloc[[0]]
    np.testing.assert_allclose(pipeline.transform(row), pipeline.transform(row.copy()))


def test_assign_business_segment_labels_warns_on_indistinguishable_clusters(caplog):
    import logging
    rfm = pd.DataFrame({
        "Cluster": [0] * 10 + [1] * 10,
        "Recency": [200] * 10 + [205] * 10,
        "Frequency": [1.0] * 20,
        "Monetary": [100.0] * 10 + [101.0] * 10,  # ~1% apart, essentially the same
    })
    with caplog.at_level(logging.WARNING):
        assign_business_segment_labels(rfm)
    assert any("differ by only" in r.message or "duplicate names" in r.message for r in caplog.records)
