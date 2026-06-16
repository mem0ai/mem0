"""Persistent write queue access layer.

Implements the ``WriteQueue`` interface described in the TechSpec
("Design de Implementação → Interfaces Principais"). It decouples the MCP
``add_memories`` tool from the (slow) LLM extraction performed by the background
worker: writes are validated and enqueued (returning an immediate ack/job_id),
and a worker later consumes the queue.

Persistence is SQLite-backed through the existing SQLAlchemy stack
(``app.database``), so enqueued jobs survive process restarts.
"""

import uuid
from dataclasses import dataclass
from typing import List, Optional

from app.database import SessionLocal
from app.models import WriteQueueJob as WriteQueueModel
from app.models import WriteQueueStatus
from sqlalchemy.orm import Session


@dataclass
class WriteJob:
    """A single write request enqueued for asynchronous LLM extraction."""
    id: str           # tracking id returned in the ack
    project: str      # target space/project (auto-cataloged)
    hostname: str     # identity (attribution/audit)
    client_name: str  # originating MCP client/agent
    text: str         # raw content for LLM extraction
    created_at: str
    attempts: int = 0  # processing attempts already made (retry bookkeeping)


def _to_job(row: WriteQueueModel) -> WriteJob:
    """Map a persisted row to the in-memory ``WriteJob`` dataclass."""
    return WriteJob(
        id=str(row.id),
        project=row.project,
        hostname=row.hostname,
        client_name=row.client_name,
        text=row.text,
        created_at=row.created_at.isoformat() if row.created_at else "",
        attempts=row.attempts or 0,
    )


class WriteQueue:
    """SQLite-backed implementation of the ``WriteQueue`` protocol.

    Each public method opens a short-lived session (via ``SessionLocal`` by
    default) and commits the state transition so that progress is durable. A
    custom ``session_factory`` can be injected for testing against a temporary
    database.
    """

    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def _session(self) -> Session:
        return self._session_factory()

    def enqueue(self, job: WriteJob) -> str:
        """Persist a new job with status ``queued`` and return its ``job_id``."""
        db = self._session()
        try:
            row = WriteQueueModel(
                id=uuid.UUID(job.id) if job.id else uuid.uuid4(),
                project=job.project,
                hostname=job.hostname,
                client_name=job.client_name,
                text=job.text,
                status=WriteQueueStatus.queued,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return str(row.id)
        finally:
            db.close()

    def dequeue(self, limit: int = 1) -> List[WriteJob]:
        """Return up to ``limit`` ``queued`` jobs, marking them ``processing``.

        Jobs are returned oldest-first (FIFO) and the transition to
        ``processing`` is committed before returning, so a crash after dequeue
        does not silently re-deliver the same job as ``queued``.
        """
        db = self._session()
        try:
            rows = (
                db.query(WriteQueueModel)
                .filter(WriteQueueModel.status == WriteQueueStatus.queued)
                .order_by(WriteQueueModel.created_at.asc())
                .limit(limit)
                .all()
            )
            jobs = []
            for row in rows:
                row.status = WriteQueueStatus.processing
                jobs.append(_to_job(row))
            db.commit()
            return jobs
        finally:
            db.close()

    def mark_done(self, job_id: str) -> None:
        """Transition a job to ``done``."""
        self._set_status(job_id, WriteQueueStatus.done)

    def mark_failed(self, job_id: str, error: str, attempts: Optional[int] = None) -> None:
        """Transition a job to ``failed`` (terminal) and record the ``error``.

        ``attempts`` (when provided) records how many processing attempts were
        made before giving up, for diagnostics.
        """
        self._set_status(
            job_id, WriteQueueStatus.failed, error=error, attempts=attempts
        )

    def requeue(self, job_id: str, error: str, attempts: int) -> None:
        """Put a job back in ``queued`` for another attempt (retry).

        Records the last ``error`` and the incremented ``attempts`` count so the
        worker can stop retrying once the configured ceiling is reached. The job
        is never lost: it stays in the table, becoming eligible for ``dequeue``
        again on the next pass.
        """
        self._set_status(
            job_id, WriteQueueStatus.queued, error=error, attempts=attempts
        )

    def depth(self) -> int:
        """Return the number of pending (``queued`` or ``processing``) jobs."""
        db = self._session()
        try:
            return (
                db.query(WriteQueueModel)
                .filter(
                    WriteQueueModel.status.in_(
                        [WriteQueueStatus.queued, WriteQueueStatus.processing]
                    )
                )
                .count()
            )
        finally:
            db.close()

    def _set_status(
        self,
        job_id: str,
        status: WriteQueueStatus,
        error: Optional[str] = None,
        attempts: Optional[int] = None,
    ) -> None:
        db = self._session()
        try:
            row = (
                db.query(WriteQueueModel)
                .filter(WriteQueueModel.id == uuid.UUID(str(job_id)))
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


# Default instance backed by the application's SessionLocal. The worker
# (task_06) and add_memories (task_07) import this.
write_queue = WriteQueue()
