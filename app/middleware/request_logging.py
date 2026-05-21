"""Attach client IP to request state and log each completed request."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.client_ip import get_client_ip

logger = logging.getLogger("calovia.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = get_client_ip(request)
        request.state.client_ip = client_ip

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)

        log_msg = (
            "ip=%s method=%s path=%s status=%s duration_ms=%s"
            % (client_ip, request.method, request.url.path, response.status_code, duration_ms)
        )
        if response.status_code >= 500:
            logger.error("request_completed %s", log_msg)
        elif response.status_code >= 400:
            logger.warning("request_completed %s", log_msg)
        else:
            logger.info("request_completed %s", log_msg)

        return response
