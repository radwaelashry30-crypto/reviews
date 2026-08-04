from __future__ import annotations

from pydantic import BaseModel, Field


class RfmPredictionRequest(BaseModel):
    recency: float = Field(..., ge=0, description="Days since the customer's last order")
    frequency: float = Field(..., ge=1, description="Number of distinct orders")
    monetary: float = Field(..., ge=0, description="Total spend across orders (BRL)")


class RfmPredictionResponse(BaseModel):
    cluster_id: int
    segment_name: str
    input: dict
