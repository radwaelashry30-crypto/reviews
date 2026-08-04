"""Standard API response envelope, used by every endpoint."""
from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    api_version: str = "v1"
    model_version: str | None = None
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: Meta = Field(default_factory=Meta)


def envelope(data, model_version: str | None = None) -> dict:
    return {"success": True, "data": data, "meta": Meta(model_version=model_version).model_dump()}
