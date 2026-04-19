from __future__ import annotations

from datetime import datetime, timedelta, timezone

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

    def oldest_pending_age_seconds(self, *, now: datetime | None = None) -> float | None:
        effective_now = now or _utcnow()
        stmt = select(func.min(Job.available_at)).where(Job.status == "pending")
        oldest = self.session.execute(stmt).scalar_one_or_none()
        if oldest is None:
            return None
        return max((effective_now - self._normalize_datetime(oldest)).total_seconds(), 0.0)

    def count_stalled_running(self, *, stale_after_seconds: float, now: datetime | None = None) -> int:
        effective_now = now or _utcnow()
        stale_started_before = effective_now - timedelta(seconds=stale_after_seconds)
        stmt = (
            select(Job.started_at)
            .where(Job.status == "running")
            .where(Job.started_at.is_not(None))
        )
        started_at_values = self.session.execute(stmt).scalars().all()
        return sum(
            1
            for started_at in started_at_values
            if self._normalize_datetime(started_at) <= stale_started_before
        )

    @staticmethod
    def _normalize_datetime(value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
