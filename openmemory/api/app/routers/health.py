"""Operational health endpoint for load balancers and bootstrap gates."""

import logging
import os

from app.database import SessionLocal
from app.utils.write_queue import write_queue
from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(tags=["operations"])
logger = logging.getLogger(__name__)


def _check_database() -> tuple[str, str | None]:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return "ok", None
    except Exception as exc:  # noqa: BLE001
        return "error", str(exc)
    finally:
        db.close()


def _check_qdrant() -> tuple[str, str | None]:
    host = os.getenv("QDRANT_HOST", "mem0_store")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://{host}:{port}/readyz", timeout=2) as resp:
            if resp.status == 200:
                return "ok", None
            return "error", f"status {resp.status}"
    except Exception as exc:  # noqa: BLE001
        return "error", str(exc)


def _check_memory_client() -> tuple[str, str | None]:
    try:
        from app.utils.memory import get_memory_client_safe

        client = get_memory_client_safe()
        if client is None:
            return "degraded", "memory client unavailable"
        return "ok", None
    except Exception as exc:  # noqa: BLE001
        return "error", str(exc)


def _check_queue() -> tuple[str, dict]:
    try:
        depth = write_queue.depth()
        return "ok", {"depth": depth}
    except Exception as exc:  # noqa: BLE001
        return "error", {"depth": None, "error": str(exc)}


@router.get("/health")
async def health(response: Response):
    """Liveness/readiness: DB, Qdrant, mem0 client, queue depth."""
    checks: dict[str, object] = {}
    unhealthy = False
    degraded = False

    db_status, db_err = _check_database()
    checks["database"] = {"status": db_status, "error": db_err}
    unhealthy |= db_status == "error"

    qdrant_status, qdrant_err = _check_qdrant()
    checks["qdrant"] = {"status": qdrant_status, "error": qdrant_err}
    unhealthy |= qdrant_status == "error"

    mem_status, mem_err = _check_memory_client()
    checks["memory_client"] = {"status": mem_status, "error": mem_err}
    degraded |= mem_status == "degraded"
    unhealthy |= mem_status == "error"

    queue_status, queue_info = _check_queue()
    checks["write_queue"] = {"status": queue_status, **queue_info}
    unhealthy |= queue_status == "error"

    overall = "unhealthy" if unhealthy else ("degraded" if degraded else "healthy")
    payload = {"status": overall, "checks": checks}
    status_code = 503 if unhealthy else 200
    response.status_code = status_code
    return JSONResponse(content=payload, status_code=status_code)
