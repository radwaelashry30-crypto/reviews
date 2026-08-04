import math

import pytest


def _repo_ready(client) -> bool:
    resp = client.get("/api/v1/analytics/summary")
    return resp.status_code == 200


def test_analytics_summary_json_serializable(client):
    if not _repo_ready(client):
        pytest.skip("Analytics results not generated in this environment; run run_pipeline.py first.")
    resp = client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_unique_orders"] > 0
    # every numeric field must be finite (no NaN/Infinity leaked into JSON)
    for key, value in data.items():
        if isinstance(value, float):
            assert math.isfinite(value), f"{key} is not finite: {value}"


def test_monthly_orders_endpoint(client):
    resp = client.get("/api/v1/analytics/orders/monthly")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_monthly_revenue_endpoint(client):
    resp = client.get("/api/v1/analytics/revenue/monthly")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_customers_summary_endpoint(client):
    resp = client.get("/api/v1/customers/summary")
    assert resp.status_code in (200, 404)


def test_top_cities_endpoint(client):
    resp = client.get("/api/v1/customers/top-cities?n=5")
    if resp.status_code == 200:
        assert len(resp.json()["data"]) <= 5


def test_rfm_segmentation_predict_input_validation(client):
    resp = client.post("/api/v1/segmentation/predict", json={"recency": -5, "frequency": 1, "monetary": 100})
    assert resp.status_code == 422  # recency must be >= 0
