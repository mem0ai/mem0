from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.jobs import JobRepository
from app.schemas.observability import JobStats, ObservabilityStats
from app.telemetry.metrics import render_prometheus_metrics, snapshot_metrics


class ObservabilityService:
    def __init__(self, session: Session):
        self.session = session
        self.jobs = JobRepository(session)

    def metrics_payload(self) -> str:
        return render_prometheus_metrics(
            counters=snapshot_metrics(),
            job_status_counts=self._job_status_counts(),
            job_type_status_counts=self.jobs.count_by_type_and_status(),
        )

    def stats(self) -> ObservabilityStats:
        metrics = snapshot_metrics()
        by_status = self._job_status_counts()
        by_type_status = self.jobs.count_by_type_and_status()
        by_type: dict[str, dict[str, int]] = {}
        for (job_type, status), count in by_type_status.items():
            by_type.setdefault(job_type, {})[status] = count

        return ObservabilityStats(
            metrics=metrics,
            jobs=JobStats(
                by_status=by_status,
                by_type=by_type,
            ),
        )

    def _job_status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in ("pending", "running", "completed", "failed")}
        counts.update(self.jobs.count_by_status())
        return counts
