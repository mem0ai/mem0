from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.models.episode import Episode
from app.repositories.jobs import JobRepository
from app.repositories.memory_units import MemoryUnitRepository
from app.services.consolidation import ConsolidationService
from app.services.lifecycle import LifecycleService
from app.telemetry.metrics import increment_metric


class WorkerRunner:
    @classmethod
    def run_pending_jobs(cls) -> int:
        session_factory = get_session_factory()
        processed = 0
        session: Session = session_factory()
        try:
            jobs = JobRepository(session)
            consolidation = ConsolidationService(session)
            lifecycle = LifecycleService(session)
            memory_units = MemoryUnitRepository(session)

            for job in jobs.list_pending():
                jobs.mark_running(job)
                try:
                    if job.job_type == "memory_consolidation":
                        episode = session.get(Episode, job.payload_json["episode_id"])
                        if episode is None:
                            raise LookupError("Episode not found for consolidation job")
                        space_type = job.payload_json["space_type"]
                        consolidation.consolidate_episode(episode, space_type)
                    elif job.job_type in {"memory_decay", "memory_eviction"}:
                        memory_unit = memory_units.get_by_id(job.payload_json["memory_unit_id"])
                        if memory_unit is None:
                            raise LookupError("Memory unit not found for lifecycle job")
                        lifecycle.apply_transition(
                            memory_unit=memory_unit,
                            space_type=job.payload_json["space_type"],
                        )
                    jobs.mark_completed(job)
                    increment_metric("jobs_processed_total")
                    session.commit()
                    processed += 1
                except Exception as exc:  # noqa: BLE001
                    jobs.mark_failed(job, str(exc))
                    increment_metric("jobs_failed_total")
                    session.commit()
                    raise
            return processed
        finally:
            session.close()
