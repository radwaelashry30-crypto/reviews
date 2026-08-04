"""RFM segmentation business logic."""
from __future__ import annotations

from app.core.exceptions import ResourceNotFoundError
from app.ml.segmentation import predict_segment
from app.repositories.analytics_repository import AnalyticsRepository
from app.services.model_registry import ModelRegistry


def get_rfm_summary(repo: AnalyticsRepository) -> dict:
    payload = repo.get_json("rfm_segments")
    if payload is None:
        raise ResourceNotFoundError("RFM segmentation results have not been generated yet.")
    return payload


def predict_customer_segment(registry: ModelRegistry, recency: float, frequency: float, monetary: float) -> dict:
    scaler, kmeans, cluster_label_map = registry.require_rfm()
    prediction = predict_segment(scaler, kmeans, cluster_label_map, recency, frequency, monetary)
    return {**prediction, "input": {"recency": recency, "frequency": frequency, "monetary": monetary}}
