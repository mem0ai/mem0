from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.jobs import JobRepository
from app.schemas.observability import JobStats, ObservabilityStats
from app.telemetry.metrics import render_prometheus_metrics, snapshot_metrics


class ObservabilityService:
    def __init__(self, session: Session):
        self.session = session
        self.jobs = JobRepository(session)
        self.audit = AuditLogRepository(session)
        self.settings = get_settings()

    def metrics_payload(self) -> str:
        return render_prometheus_metrics(
            counters=self._metrics_snapshot(),
            job_status_counts=self._job_status_counts(),
            job_type_status_counts=self.jobs.count_by_type_and_status(),
        )

    def stats(self) -> ObservabilityStats:
        metrics = self._metrics_snapshot()
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
                oldest_pending_age_seconds=self.jobs.oldest_pending_age_seconds(),
                stalled_running_count=self.jobs.count_stalled_running(
                    stale_after_seconds=self.settings.stalled_job_after_seconds
                ),
            ),
        )

    def _job_status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in ("pending", "running", "completed", "failed")}
        counts.update(self.jobs.count_by_status())
        return counts

    def _metrics_snapshot(self) -> dict[str, int]:
        metrics = snapshot_metrics()
        metrics.update(self._shared_operational_metrics())
        return metrics

    def _shared_operational_metrics(self) -> dict[str, int]:
        audit_counts = self.audit.count_by_action(
            [
                "memory_unit_created",
                "memory_unit_merged",
                "memory_unit_decayed",
                "memory_unit_archived",
                "memory_unit_evicted",
            ]
        )
        job_counts = self._job_status_counts()
        return {
            "consolidation_created_total": audit_counts.get("memory_unit_created", 0),
            "consolidation_merged_total": audit_counts.get("memory_unit_merged", 0),
            "jobs_processed_total": job_counts.get("completed", 0),
            "jobs_failed_total": job_counts.get("failed", 0),
            "lifecycle_decayed_total": audit_counts.get("memory_unit_decayed", 0),
            "lifecycle_archived_total": audit_counts.get("memory_unit_archived", 0),
            "lifecycle_evicted_total": audit_counts.get("memory_unit_evicted", 0),
        }
