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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.utils.metrics import PROJECT_MEMORY_COUNT, PROJECT_SIZE_OVER_THRESHOLD

router = APIRouter(prefix="/admin", tags=["admin"])


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
