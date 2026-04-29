"""Prometheus telemetry middleware for FastAPI."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.responses import Response as StarletteResponse

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

# ============================================================================
# Prometheus Metrics
# ============================================================================

# Total number of requests
requests_total = Counter(
    "requests_total",
    "Total number of HTTP requests",
    ["endpoint", "method", "status_code"],
)

# Request latency histogram (for p50, p95, etc.)
request_latency_seconds = Histogram(
    "request_latency_seconds",
    "HTTP request latency in seconds",
    ["endpoint", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Total number of errors
errors_total = Counter(
    "errors_total",
    "Total number of HTTP errors",
    ["endpoint", "error_type"],
)

# AI tool calls counter (emitted from /ai/chat endpoint)
ai_tool_calls_total = Counter(
    "ai_tool_calls_total",
    "Total number of AI tool calls",
    ["tool_name", "status"],
)


# ============================================================================
# Middleware
# ============================================================================


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to track request metrics with Prometheus."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[StarletteResponse]]) -> StarletteResponse:
        """Process request and record metrics.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            HTTP response with metrics recorded.
        """
        # Get endpoint path (use path template when available)
        endpoint = request.url.path
        method = request.method

        # Start timing
        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate latency
        latency = time.perf_counter() - start_time

        # Record metrics
        status_code = str(response.status_code)
        requests_total.labels(endpoint=endpoint, method=method, status_code=status_code).inc()
        request_latency_seconds.labels(endpoint=endpoint, method=method).observe(latency)

        # Track errors (4xx and 5xx)
        if response.status_code >= 400:
            error_type = "4xx" if response.status_code < 500 else "5xx"
            errors_total.labels(endpoint=endpoint, error_type=error_type).inc()

        return response


def telemetry_middleware() -> type[PrometheusMiddleware]:
    """Create and return telemetry middleware class.

    Returns:
        PrometheusMiddleware class.
    """
    return PrometheusMiddleware
