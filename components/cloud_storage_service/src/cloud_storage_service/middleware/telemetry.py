"""Prometheus telemetry middleware for FastAPI."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.responses import Response as StarletteResponse


# ============================================================================
# Prometheus Metrics
# ============================================================================

_NAMESPACE = "storage_service"

# Single source of truth for HTTP requests. Use status_code label to query
# error rate (e.g., status_code=~"5..") instead of a separate errors counter.
requests_total = Counter(
    f"{_NAMESPACE}_requests_total",
    "Total number of HTTP requests",
    ["endpoint", "method", "status_code", "error_class"],
)

request_latency_seconds = Histogram(
    f"{_NAMESPACE}_request_latency_seconds",
    "HTTP request latency in seconds",
    ["endpoint", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# AI tool calls — populated by the /ai/chat handler from AIResponse.tool_calls.
ai_tool_calls_total = Counter(
    f"{_NAMESPACE}_ai_tool_calls_total",
    "Total number of AI tool calls dispatched by the AI client",
    ["tool_name", "status"],
)


# ============================================================================
# Middleware
# ============================================================================


def _get_route_template(request: Request) -> str:
    """Return the FastAPI route template (e.g., '/download/{key:path}').

    Falls back to 'unknown' when the request didn't match any route — this
    prevents high-cardinality leaks from raw paths like '/download/user/file.txt'.

    Args:
        request: Incoming HTTP request.

    Returns:
        Route template string, or 'unknown' if no route matched.
    """
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(route.path)
    return "unknown"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware that records request count, latency, and error metrics.

    Endpoint labels use the FastAPI route template (e.g., '/download/{key:path}'),
    NOT the raw URL path. This keeps Prometheus cardinality bounded regardless of
    how many distinct object keys clients request.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[StarletteResponse]],
    ) -> StarletteResponse:
        """Process the request and record metrics, including for unhandled exceptions.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            HTTP response with metrics recorded.

        Note:
            When an exception occurs, we distinguish between:
            - endpoint="unknown" (no matching route): indicates infrastructure issue
            - endpoint!="unknown" (route matched but handler failed): indicates handler error
        """
        method = request.method
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            latency = time.perf_counter() - start_time
            endpoint = _get_route_template(request)
            error_class = "infra" if endpoint == "unknown" else "handler"
            requests_total.labels(
                endpoint=endpoint,
                method=method,
                status_code="500",
                error_class=error_class,
            ).inc()
            request_latency_seconds.labels(
                endpoint=endpoint,
                method=method,
            ).observe(latency)
            raise

        latency = time.perf_counter() - start_time
        endpoint = _get_route_template(request)
        status_code = response.status_code
        if status_code < 400:
            error_class = "success"
        elif status_code < 500 and endpoint != "unknown":
            error_class = "domain"
        else:
            error_class = "infra"
        requests_total.labels(
            endpoint=endpoint,
            method=method,
            status_code=str(status_code),
            error_class=error_class,
        ).inc()
        request_latency_seconds.labels(
            endpoint=endpoint,
            method=method,
        ).observe(latency)

        return response
