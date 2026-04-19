from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.schemas.observability import ObservabilityStats
from app.services.observability import ObservabilityService

router = APIRouter(tags=["observability"])

api_router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/metrics")
def metrics(db: Session = Depends(get_db_session)) -> Response:
    service = ObservabilityService(db)
    return Response(
        content=service.metrics_payload(),
        media_type="text/plain; version=0.0.4",
    )


@api_router.get("/stats", response_model=ObservabilityStats)
def stats(db: Session = Depends(get_db_session)) -> ObservabilityStats:
    service = ObservabilityService(db)
    return service.stats()
