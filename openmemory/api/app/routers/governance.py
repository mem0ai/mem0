"""Admin governance endpoints (task_11)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from app.database import get_db
from app.governance.quality_eval import get_last_quality
from app.models import MemoryState, MemoryStatusHistory, Project
from app.utils.governance_policy import (
    get_global_policy,
    get_project_override,
    list_policies,
    save_global_policy,
    save_project_override,
    validate_policy_document,
)
from app.utils.governance_queue import governance_queue
from app.utils.quarantine import QuarantineEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/governance", tags=["governance"])


class PolicyUpdate(BaseModel):
    policy: Dict[str, Any]


class EnqueueJobRequest(BaseModel):
    project: Optional[str] = None
    limit: int = 500


def _engine() -> QuarantineEngine:
    return QuarantineEngine()


@router.get("/policies")
def get_policies(db: Session = Depends(get_db)) -> dict:
    return list_policies(session_factory=lambda: db)


@router.put("/policies")
def put_global_policy(body: PolicyUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        saved = save_global_policy(db, body.policy)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"global": saved}


@router.put("/policies/{project}")
def put_project_policy(project: str, body: PolicyUpdate, db: Session = Depends(get_db)) -> dict:
    if db.query(Project).filter(Project.name == project).first() is None:
        raise HTTPException(status_code=404, detail=f"project '{project}' not found")
    try:
        validate_policy_document({**get_global_policy(db), **body.policy})
        saved = save_project_override(db, project, body.policy)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project": project, "overrides": saved}


@router.post("/jobs/{job_type}", status_code=202)
def enqueue_job(job_type: str, body: EnqueueJobRequest) -> dict:
    allowed = {"dedup", "ttl_prune", "consolidate", "purge"}
    if job_type not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported job_type '{job_type}'")
    job_id = governance_queue.enqueue(
        job_type,
        project=body.project,
        payload={"limit": body.limit, "manual": True},
    )
    return {"job_id": job_id, "job_type": job_type, "status": "queued"}


@router.get("/audit")
def governance_audit(
    db: Session = Depends(get_db),
    project: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    query = db.query(MemoryStatusHistory).order_by(MemoryStatusHistory.changed_at.desc())
    if state:
        try:
            target = MemoryState(state)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid state '{state}'") from exc
        query = query.filter(MemoryStatusHistory.new_state == target)
    if since:
        query = query.filter(MemoryStatusHistory.changed_at >= since)
    if until:
        query = query.filter(MemoryStatusHistory.changed_at <= until)
    rows = query.limit(limit).all()
    items = []
    for row in rows:
        mem = row.memory_id
        items.append(
            {
                "memory_id": str(row.memory_id),
                "old_state": row.old_state.value,
                "new_state": row.new_state.value,
                "changed_at": row.changed_at.isoformat() if row.changed_at else None,
                "changed_by": str(row.changed_by),
            }
        )
    if project:
        # Filter in Python — history table has no project column.
        from app.models import Memory

        mem_ids = {
            str(m.id)
            for m in db.query(Memory).all()
            if (m.metadata_ or {}).get("project") == project
        }
        items = [i for i in items if i["memory_id"] in mem_ids]
    return {"items": items}


@router.post("/revert/{memory_id}")
def revert_memory(memory_id: UUID, engine: QuarantineEngine = Depends(_engine)) -> dict:
    ok = engine.revert(memory_id)
    if not ok:
        raise HTTPException(status_code=409, detail="memory is not quarantined or not found")
    return {"memory_id": str(memory_id), "state": "active"}


@router.get("/quality")
def governance_quality() -> dict:
    return get_last_quality()
