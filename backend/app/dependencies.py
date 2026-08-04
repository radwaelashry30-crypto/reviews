"""FastAPI dependency providers — pull shared state off `request.app.state`."""
from __future__ import annotations

from fastapi import Request

from app.repositories.analytics_repository import AnalyticsRepository
from app.services.model_registry import ModelRegistry


def get_model_registry(request: Request) -> ModelRegistry:
    return request.app.state.model_registry


def get_analytics_repository(request: Request) -> AnalyticsRepository:
    return request.app.state.analytics_repository
