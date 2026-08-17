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


class FullPipelineRequest(BaseModel):
    """Task 1 (sentiment) -> Task 2 (fake check, only if Negative) -> Task 3 (aspects, always)."""
    text: str = Field(..., min_length=1, max_length=2000)
    model_name: ModelName = "bert"
    source_language: Literal["en", "pt"] = "en"
    translate: bool = False
    aspects: list[str] | None = None

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class FullPipelineResponse(BaseModel):
    sentiment: SentimentPrediction
    fake_check: dict | None
    aspects: dict


class ExplainRequest(BaseModel):
    """SHAP explanation for a single review, BERT only."""
    text: str = Field(..., min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class ExplainResponse(BaseModel):
    available: bool
    reason: str | None = None
    top_tokens_toward_positive: list[dict] | None = None


class FeedbackRequest(BaseModel):
    """Thumbs-up/down on a saved prediction. This project has no user
    accounts, so feedback is anonymous -- a directional signal, not an
    audited per-user record."""
    is_correct: bool
    comment: str | None = Field(default=None, max_length=1000)
