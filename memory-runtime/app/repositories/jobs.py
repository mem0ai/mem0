from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.job import Job


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, *, job_type: str, payload_json: dict) -> Job:
        job = Job(job_type=job_type, payload_json=payload_json)
        self.session.add(job)
        self.session.flush()
        return job

    def list_pending(self) -> list[Job]:
        stmt: Select[tuple[Job]] = (
            select(Job)
            .where(Job.status == "pending")
            .where(Job.available_at <= _utcnow())
            .order_by(Job.available_at.asc(), Job.id.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def mark_running(self, job: Job) -> None:
        job.status = "running"
        job.attempt_count += 1
        job.started_at = _utcnow()
        self.session.flush()

    def mark_completed(self, job: Job) -> None:
        job.status = "completed"
        job.finished_at = _utcnow()
        self.session.flush()

    def mark_failed(self, job: Job, error_text: str) -> None:
        job.status = "failed"
        job.error_text = error_text
        job.finished_at = _utcnow()
        self.session.flush()

    def count_by_status(self) -> dict[str, int]:
        stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
        return {
            status: count
            for status, count in self.session.execute(stmt).all()
        }

    def count_by_type_and_status(self) -> dict[tuple[str, str], int]:
        stmt = select(Job.job_type, Job.status, func.count(Job.id)).group_by(Job.job_type, Job.status)
        return {
            (job_type, status): count
            for job_type, status, count in self.session.execute(stmt).all()
        }
