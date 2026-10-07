from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from db import SessionLocal

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/api/health", response_model=HealthResponse)
def health_check():
    """Liveness/readiness probe for load balancers and orchestrators.

    Intentionally unauthenticated and not rate limited: probes must work
    before any admin is configured. The error body is a fixed shape so a
    failed probe can never leak connection strings or other internals.
    """
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected"},
        )
    return HealthResponse(status="ok", database="connected")
