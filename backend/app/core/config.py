"""Central, validated application settings. Every environment variable is read here only.

Paths default to project-relative locations (via `PROJECT_ROOT`), never a
machine-specific absolute path. Override any of them with an `.env` file or
real environment variables (see `.env.example` at the project root).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> <project root>
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Baseera"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    FRONTEND_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"])

    DATA_DIR: Path = PROJECT_ROOT / "data"
    PROCESSED_DATA_DIR: Path = PROJECT_ROOT / "data" / "processed"
    MODEL_DIR: Path = PROJECT_ROOT / "models"
    ARTIFACT_DIR: Path = PROJECT_ROOT / "artifacts"
    RESULTS_DIR: Path = PROJECT_ROOT / "results"

    BERT_MODEL_PATH: Path = PROJECT_ROOT / "models" / "bert_review_sentiment"
    CNN_CHECKPOINT_PATH: Path = PROJECT_ROOT / "models" / "cnn2d_review_sentiment.pt"
    CNN_TOKENIZER_PATH: Path = PROJECT_ROOT / "artifacts" / "cnn2d_tokenizer.pkl"
    RFM_SCALER_PATH: Path = PROJECT_ROOT / "artifacts" / "rfm_scaler.pkl"
    RFM_MODEL_PATH: Path = PROJECT_ROOT / "artifacts" / "rfm_kmeans.pkl"

    DEFAULT_SENTIMENT_MODEL: str = "bert"
    # BERT (670MB weights) needs well over 512MB RAM once loaded alongside
    # PyTorch's own baseline footprint -- too much for free-tier hosts like
    # Render's free web service. ENABLE_BERT=false skips loading it entirely
    # (not just letting the load fail) so a low-RAM deployment doesn't get
    # OOM-killed attempting to load a model it can't fit. CNN2D (~12MB) is
    # unaffected either way.
    ENABLE_BERT: bool = True
    ENABLE_CNN2D: bool = True
    ENABLE_TRANSLATION: bool = False
    ALLOW_EXTERNAL_MODEL_DOWNLOADS: bool = False
    MAX_REVIEW_LENGTH: int = 2000
    MAX_BATCH_SIZE: int = 64

    LOG_LEVEL: str = "INFO"

    # Optional relational persistence (sentiment-analysis history, feedback,
    # durable batch-upload records). Entirely optional -- the app runs fine
    # with this unset, same philosophy as ENABLE_BERT/ALLOW_EXTERNAL_MODEL_DOWNLOADS.
    # When unset, upload_store.py falls back to its original local-JSON store.
    DATABASE_URL: str | None = None


settings = Settings()
