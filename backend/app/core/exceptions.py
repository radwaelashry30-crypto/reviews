"""Central exception types and FastAPI exception handlers -> the standard API response envelope."""
from __future__ import annotations

import uuid

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error. Carries an HTTP status and a machine-readable error code."""

    def __init__(self, message: str, code: str, status_code: int = 500, details: dict | None = None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ModelUnavailableError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="MODEL_NOT_AVAILABLE", status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details)


class InvalidRequestError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="INVALID_REQUEST", status_code=status.HTTP_400_BAD_REQUEST, details=details)


class ResourceNotFoundError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND, details=details)


class ProcessingTimeoutError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="PROCESSING_TIMEOUT", status_code=status.HTTP_504_GATEWAY_TIMEOUT, details=details)


def _error_envelope(code: str, message: str, details: dict, request_id: str) -> dict:
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
        "meta": {"request_id": request_id},
    }


def register_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        request_id = str(uuid.uuid4())
        return JSONResponse(status_code=exc.status_code, content=_error_envelope(exc.code, exc.message, exc.details, request_id))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        request_id = str(uuid.uuid4())
        # Pydantic v2 puts the raw exception instance (e.g. a ValueError raised by a
        # @field_validator) in each error's "ctx", which json.dumps cannot serialize.
        # jsonable_encoder doesn't know how to convert it either, so strip/stringify it.
        safe_errors = []
        for err in exc.errors():
            err = dict(err)
            ctx = err.get("ctx")
            if isinstance(ctx, dict):
                err["ctx"] = {k: (str(v) if isinstance(v, BaseException) else v) for k, v in ctx.items()}
            safe_errors.append(err)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_envelope("VALIDATION_ERROR", "Request validation failed.", {"errors": jsonable_encoder(safe_errors)}, request_id),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = str(uuid.uuid4())
        # Never expose raw stack traces to the client.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_envelope("INTERNAL_ERROR", "An unexpected error occurred.", {}, request_id),
        )
