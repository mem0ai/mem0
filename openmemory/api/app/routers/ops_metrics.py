"""Prometheus metrics endpoint (scale architecture observability)."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# Import registers custom collectors with the default registry before scrape.
from app.utils import metrics as _metrics  # noqa: F401

router = APIRouter(tags=["operations"])


@router.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
