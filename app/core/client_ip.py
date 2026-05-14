"""Trusted client IP for logging and rate limits (supports reverse proxies)."""

from __future__ import annotations

from starlette.requests import Request


def get_client_ip(request: Request) -> str:
    """
    Prefer X-Forwarded-For (first hop), then X-Real-IP, then the direct client.
    When running behind a trusted proxy, ensure the proxy strips/spoofed headers
    or that you only trust this value from your load balancer.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"
