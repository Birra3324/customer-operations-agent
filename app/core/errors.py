"""Safe HTTP exception handlers. Never leak internals to clients."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_request_id

log = logging.getLogger("ops.errors")


def _json_safe(value: object) -> object:
    """Pydantic may put a ValueError on validation ctx. Responses stay JSON."""
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exc(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        rid = getattr(request.state, "request_id", None) or get_request_id()
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "request_id": rid},
            headers=getattr(exc, "headers", None) or {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exc(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = getattr(request.state, "request_id", None) or get_request_id()
        # Do not log the submitted body; validation details stay on the response only.
        log.info("validation_failed")
        return JSONResponse(
            status_code=422,
            content={"error": "Validation failed", "details": _json_safe(exc.errors()), "request_id": rid},
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", None) or get_request_id()
        log.error("unhandled error_type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": rid},
        )
