"""
Automatos Shared Metrics — Prometheus Exporter for All Services
===============================================================

Exposes a /metrics endpoint compatible with Prometheus scraping.
Works with both FastAPI and aiohttp.

FastAPI usage:
    from automatos_metrics import add_fastapi_metrics
    app = FastAPI()
    add_fastapi_metrics(app, service="my-service")

aiohttp usage:
    from automatos_metrics import add_aiohttp_metrics
    app = web.Application()
    add_aiohttp_metrics(app, service="my-service")

Requires: prometheus_client
"""

import time
from typing import Optional

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        REGISTRY,
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


def _create_metrics(service: str, registry=None):
    """Create standard metrics for a service."""
    if not HAS_PROMETHEUS:
        return None

    reg = registry or REGISTRY
    prefix = service.replace("-", "_").replace(" ", "_")

    return {
        "requests_total": Counter(
            f"{prefix}_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
            registry=reg,
        ),
        "request_duration": Histogram(
            f"{prefix}_request_duration_seconds",
            "Request latency in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=reg,
        ),
        "in_progress": Gauge(
            f"{prefix}_requests_in_progress",
            "Requests currently being processed",
            registry=reg,
        ),
        "info": Info(
            f"{prefix}_build",
            "Service build info",
            registry=reg,
        ),
    }


# ---------------------------------------------------------------------------
# FastAPI integration
# ---------------------------------------------------------------------------

def add_fastapi_metrics(app, service: str = "unknown"):
    """Add Prometheus /metrics endpoint + request middleware to a FastAPI app.

    Args:
        app: FastAPI application instance
        service: Service name for metric prefixes
    """
    if not HAS_PROMETHEUS:
        import logging
        logging.getLogger(__name__).warning(
            "prometheus_client not installed — metrics disabled"
        )
        return

    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware

    metrics = _create_metrics(service)
    metrics["info"].info({"service": service})

    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.url.path == "/metrics":
                return await call_next(request)

            method = request.method
            endpoint = request.url.path

            metrics["in_progress"].inc()
            start = time.monotonic()
            try:
                response = await call_next(request)
                status = str(response.status_code)
                return response
            except Exception:
                status = "500"
                raise
            finally:
                duration = time.monotonic() - start
                metrics["in_progress"].dec()
                metrics["requests_total"].labels(method, endpoint, status).inc()
                metrics["request_duration"].labels(method, endpoint).observe(duration)

    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return Response(
            content=generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )


# ---------------------------------------------------------------------------
# aiohttp integration
# ---------------------------------------------------------------------------

def add_aiohttp_metrics(app, service: str = "unknown"):
    """Add Prometheus /metrics endpoint + request middleware to an aiohttp app.

    Args:
        app: aiohttp.web.Application instance
        service: Service name for metric prefixes
    """
    if not HAS_PROMETHEUS:
        import logging
        logging.getLogger(__name__).warning(
            "prometheus_client not installed — metrics disabled"
        )
        return

    from aiohttp import web

    metrics = _create_metrics(service)
    metrics["info"].info({"service": service})

    @web.middleware
    async def prometheus_middleware(request, handler):
        if request.path == "/metrics":
            return await handler(request)

        method = request.method
        endpoint = request.path

        metrics["in_progress"].inc()
        start = time.monotonic()
        try:
            response = await handler(request)
            status = str(response.status)
            return response
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.monotonic() - start
            metrics["in_progress"].dec()
            metrics["requests_total"].labels(method, endpoint, status).inc()
            metrics["request_duration"].labels(method, endpoint).observe(duration)

    # Prepend middleware
    app.middlewares.insert(0, prometheus_middleware)

    async def metrics_handler(request):
        return web.Response(
            body=generate_latest(REGISTRY),
            content_type=CONTENT_TYPE_LATEST,
        )

    app.router.add_get("/metrics", metrics_handler)
