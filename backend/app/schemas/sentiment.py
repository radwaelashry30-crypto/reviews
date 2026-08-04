from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ModelName = Literal["bert", "cnn2d"]


class SentimentPredictionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    model_name: ModelName = "bert"
    source_language: Literal["en", "pt"] = "en"
    translate: bool = False

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class SentimentPrediction(BaseModel):
    label: Literal["Negative", "Positive"]
    class_id: int
    probability_positive: float
    probability_negative: float
    confidence: float
    model_name: str
    source_language: str
    translated: bool
    cleaned_text: str


class BatchPredictionItem(BaseModel):
    id: str
    text: str = Field(..., min_length=1, max_length=2000)


class BatchPredictionRequest(BaseModel):
    items: list[BatchPredictionItem] = Field(..., min_length=1, max_length=64)
    model_name: ModelName = "bert"


class BatchPredictionResultItem(SentimentPrediction):
    id: str


class BatchPredictionResponse(BaseModel):
    results: list[BatchPredictionResultItem]
    n_items: int
