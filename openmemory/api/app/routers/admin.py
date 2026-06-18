"""Administrative/operational endpoints for Fase 2 partitioning.

task_09: per-project size & health visibility so operators can promote a giant
project to a dedicated shard *before* it degrades search.

The promotion threshold is parameterizable via ``PROJECT_PROMOTION_THRESHOLD``
(number of memories); a project at/above it is flagged ``over_threshold`` and
counted in the ``project_size_over_threshold`` metric.

Migration control endpoints (start/flip/rollback, promote) are added to this same
router by task_07 / task_08.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.utils.metrics import PROJECT_MEMORY_COUNT, PROJECT_SIZE_OVER_THRESHOLD
from app.utils.migration_control import MigrationControl, MigrationError, default_count_fn

router = APIRouter(prefix="/admin", tags=["admin"])


def _control() -> MigrationControl:
    """Build a MigrationControl wired to the live Qdrant count function."""
    return MigrationControl(count_fn=default_count_fn())


def promotion_threshold() -> int:
    """Memory count at/above which a project should be promoted (parameterizable)."""
    try:
        return int(os.getenv("PROJECT_PROMOTION_THRESHOLD", "10000000"))
    except ValueError:
        return 10_000_000


@router.get("/projects/sizes")
def project_sizes(db: Session = Depends(get_db)) -> dict:
    """List projects with size, partition tier/shard and proximity to the threshold."""
    threshold = promotion_threshold()
    projects = db.query(Project).all()

    items = []
    over = 0
    for p in projects:
        count = p.memory_count or 0
        is_over = count >= threshold
        if is_over:
            over += 1
        tier = p.partition_tier.value if p.partition_tier is not None else "shared"
        # Refresh per-project gauge for Prometheus scraping.
        PROJECT_MEMORY_COUNT.labels(project=p.name).set(count)
        items.append(
            {
                "name": p.name,
                "memory_count": count,
                "partition_tier": tier,
                "shard_key": p.shard_key,
                "over_threshold": is_over,
            }
        )

    PROJECT_SIZE_OVER_THRESHOLD.set(over)
    return {"threshold": threshold, "over_threshold_count": over, "projects": items}


# --------------------------------------------------------------------------- #
# Migration control (task_07 / ADR-003)
# --------------------------------------------------------------------------- #
class StartMigrationRequest(BaseModel):
    source_collection: str
    target_collection: str


@router.post("/migration/start")
def migration_start(req: StartMigrationRequest, control: MigrationControl = Depends(_control)) -> dict:
    try:
        return control.start(req.source_collection, req.target_collection)
    except MigrationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/migration/validate")
def migration_validate(control: MigrationControl = Depends(_control)) -> dict:
    try:
        return control.validate()
    except MigrationError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/migration/flip")
def migration_flip(control: MigrationControl = Depends(_control)) -> dict:
    try:
        return control.flip()
    except MigrationError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/migration/rollback")
def migration_rollback(control: MigrationControl = Depends(_control)) -> dict:
    try:
        return control.rollback()
    except MigrationError as e:
        raise HTTPException(status_code=409, detail=str(e))
