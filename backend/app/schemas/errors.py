from __future__ import annotations

from pydantic import BaseModel


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: ApiErrorDetail
    meta: dict = {}
