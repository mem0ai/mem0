from __future__ import annotations

from pydantic import BaseModel, Field


class JobStats(BaseModel):
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, dict[str, int]] = Field(default_factory=dict)
    oldest_pending_age_seconds: float | None = None
    stalled_running_count: int = 0


class ObservabilityStats(BaseModel):
    metrics: dict[str, int] = Field(default_factory=dict)
    jobs: JobStats
