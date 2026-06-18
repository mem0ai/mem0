"""Persistent governance job queue (Fase 3 task_05 / ADR-002)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.database import SessionLocal, is_postgresql
from app.models import GovernanceJob as GovernanceJobModel
from app.models import GovernanceJobStatus, GovernanceJobType
from sqlalchemy.orm import Session


@dataclass
class GovernanceJob:
    id: str
    job_type: str
    project: Optional[str]
    payload: Dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    created_at: str = ""


def _to_job(row: GovernanceJobModel) -> GovernanceJob:
    return GovernanceJob(
        id=str(row.id),
        job_type=row.job_type.value,
        project=row.project,
        payload=dict(row.payload or {}),
        attempts=row.attempts or 0,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


class GovernanceQueue:
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def _session(self) -> Session:
        return self._session_factory()

    def enqueue(
        self,
        job_type: str,
        *,
        project: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> str:
        db = self._session()
        try:
            row = GovernanceJobModel(
                id=uuid.UUID(job_id) if job_id else uuid.uuid4(),
                job_type=GovernanceJobType(job_type),
                project=project,
                status=GovernanceJobStatus.queued,
                payload=payload or {},
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return str(row.id)
        finally:
            db.close()

    def dequeue(self, limit: int = 1) -> List[GovernanceJob]:
        db = self._session()
        try:
            query = (
                db.query(GovernanceJobModel)
                .filter(GovernanceJobModel.status == GovernanceJobStatus.queued)
                .order_by(GovernanceJobModel.created_at.asc())
            )
            if is_postgresql(str(db.get_bind().url)):
                query = query.with_for_update(skip_locked=True)
            rows = query.limit(limit).all()
            jobs = []
            for row in rows:
                row.status = GovernanceJobStatus.processing
                jobs.append(_to_job(row))
            db.commit()
            return jobs
        finally:
            db.close()

    def mark_done(self, job_id: str) -> None:
        self._set_status(job_id, GovernanceJobStatus.done)

    def mark_failed(self, job_id: str, error: str, attempts: Optional[int] = None) -> None:
        self._set_status(job_id, GovernanceJobStatus.failed, error=error, attempts=attempts)

    def requeue(self, job_id: str, error: str, attempts: int) -> None:
        self._set_status(job_id, GovernanceJobStatus.queued, error=error, attempts=attempts)

    def depth(self, job_type: Optional[str] = None) -> int:
        db = self._session()
        try:
            query = db.query(GovernanceJobModel).filter(
                GovernanceJobModel.status.in_(
                    [GovernanceJobStatus.queued, GovernanceJobStatus.processing]
                )
            )
            if job_type:
                query = query.filter(
                    GovernanceJobModel.job_type == GovernanceJobType(job_type)
                )
            return query.count()
        finally:
            db.close()

    def recover_stale_processing(self) -> int:
        db = self._session()
        try:
            rows = (
                db.query(GovernanceJobModel)
                .filter(GovernanceJobModel.status == GovernanceJobStatus.processing)
                .all()
            )
            for row in rows:
                row.status = GovernanceJobStatus.queued
            if rows:
                db.commit()
            return len(rows)
        finally:
            db.close()

    def _set_status(
        self,
        job_id: str,
        status: GovernanceJobStatus,
        error: Optional[str] = None,
        attempts: Optional[int] = None,
    ) -> None:
        db = self._session()
        try:
            row = (
                db.query(GovernanceJobModel)
                .filter(GovernanceJobModel.id == uuid.UUID(str(job_id)))
                .first()
            )
            if row is None:
                return
            row.status = status
            if error is not None:
                row.error = error
            if attempts is not None:
                row.attempts = attempts
            db.commit()
        finally:
            db.close()


governance_queue = GovernanceQueue()
