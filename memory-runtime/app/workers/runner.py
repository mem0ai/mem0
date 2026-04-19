from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.models.episode import Episode
from app.repositories.jobs import JobRepository
from app.services.consolidation import ConsolidationService


class WorkerRunner:
    @classmethod
    def run_pending_jobs(cls) -> int:
        session_factory = get_session_factory()
        processed = 0
        session: Session = session_factory()
        try:
            jobs = JobRepository(session)
            consolidation = ConsolidationService(session)

            for job in jobs.list_pending():
                jobs.mark_running(job)
                try:
                    if job.job_type == "memory_consolidation":
                        episode = session.get(Episode, job.payload_json["episode_id"])
                        if episode is None:
                            raise LookupError("Episode not found for consolidation job")
                        space_type = job.payload_json["space_type"]
                        consolidation.consolidate_episode(episode, space_type)
                    jobs.mark_completed(job)
                    session.commit()
                    processed += 1
                except Exception as exc:  # noqa: BLE001
                    jobs.mark_failed(job, str(exc))
                    session.commit()
                    raise
            return processed
        finally:
            session.close()
