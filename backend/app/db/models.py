"""SQLAlchemy ORM models for the optional persistence layer.

Scope note: this project has no authentication, no user accounts, and no
"create/edit review" journey anywhere -- the Olist orders/customers/reviews
data is a static analytics dataset (parquet/JSON), not something users CRUD.
So there are deliberately no Users/Orders/Products/Auth tables here. The one
genuine persistence gap this fills: AI predictions from /predict, /pipeline,
and /explain were never saved at all, and batch-upload results
(upload_store.py) were saved as local JSON files that don't survive a
redeploy on Render's ephemeral disk. This layer covers exactly that.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_id() -> str:
    """32-char hex id, matching the format upload_store.py already used
    (uuid.uuid4().hex) -- keeps the upload_id API contract unchanged."""
    return uuid.uuid4().hex


class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    probability_positive: Mapped[float] = mapped_column(Float, nullable=False)
    probability_negative: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_name: Mapped[str] = mapped_column(String(16), nullable=False)
    source_language: Mapped[str] = mapped_column(String(8), nullable=False)
    translated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    aspects: Mapped[list["SentimentAnalysisAspect"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    feedback: Mapped[list["PredictionFeedback"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class SentimentAnalysisAspect(Base):
    __tablename__ = "sentiment_analysis_aspects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    analysis_id: Mapped[str] = mapped_column(String(32), ForeignKey("sentiment_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    aspect: Mapped[str] = mapped_column(String(64), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    analysis: Mapped["SentimentAnalysis"] = relationship(back_populates="aspects")


class PredictionFeedback(Base):
    """User-supplied thumbs-up/down on a prediction. Not tied to any account
    (this project has none) -- purely a signal for later review."""
    __tablename__ = "prediction_feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    analysis_id: Mapped[str] = mapped_column(String(32), ForeignKey("sentiment_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    analysis: Mapped["SentimentAnalysis"] = relationship(back_populates="feedback")


class BatchUploadJob(Base):
    """Durable replacement for upload_store.py's JSON-file records. Stores
    the full classify_review_file() result as JSON rather than fully
    normalizing every row into its own table -- this project's actual
    documented pain point is "results vanish on redeploy," not "we need to
    filter/query individual rows across uploads," so a JSON blob per job is
    the smallest change that fixes the real problem."""
    __tablename__ = "batch_upload_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(16), nullable=False)
    text_column_used: Mapped[str] = mapped_column(String(128), nullable=False)
    rows_processed: Mapped[int] = mapped_column(Integer, nullable=False)
    n_positive: Mapped[int] = mapped_column(Integer, nullable=False)
    n_negative: Mapped[int] = mapped_column(Integer, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
