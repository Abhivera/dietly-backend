"""Global HTTP exception handling and structured error responses."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.client_ip import get_client_ip

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    return getattr(request.state, "client_ip", None) or get_client_ip(request)


def _safe_detail(detail: Any) -> Any:
    """Ensure response body is JSON-serializable."""
    try:
        return jsonable_encoder(detail)
    except Exception:  # noqa: BLE001
        return str(detail)


def _user_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    return "See the detail field for more information."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        ip = _client_ip(request)
        logger.warning(
            "validation_error ip=%s method=%s path=%s errors=%s",
            ip,
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.errors(),
                "message": "Request validation failed",
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        ip = _client_ip(request)
        if exc.status_code >= 500:
            logger.error(
                "http_error ip=%s method=%s path=%s status=%s detail=%s",
                ip,
                request.method,
                request.url.path,
                exc.status_code,
                exc.detail,
            )
        elif exc.status_code >= 400:
            logger.warning(
                "http_error ip=%s method=%s path=%s status=%s detail=%s",
                ip,
                request.method,
                request.url.path,
                exc.status_code,
                exc.detail,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": _safe_detail(exc.detail),
                "message": _user_message(exc.detail),
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        ip = _client_ip(request)
        logger.exception(
            "unhandled_exception ip=%s method=%s path=%s",
            ip,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected error occurred.",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )
