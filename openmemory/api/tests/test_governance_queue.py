"""Tests for governance queue + worker (tasks 05–06)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, GovernanceJobStatus
from app.utils.governance_queue import GovernanceQueue


@pytest.fixture
def queue(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'gq.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    return GovernanceQueue(session_factory=factory)


def test_enqueue_dequeue_fifo(queue):
    id1 = queue.enqueue("dedup", project="p1")
    id2 = queue.enqueue("dedup", project="p2")
    jobs = queue.dequeue(limit=2)
    assert len(jobs) == 2
    assert jobs[0].id == id1
    assert jobs[1].id == id2


@pytest.mark.asyncio
async def test_process_once_marks_done(queue):
    from app.workers import governance_worker as gw

    job_id = queue.enqueue("dedup", project="p1")
    handler = MagicMock(return_value=1)
    worker = gw.GovernanceWorker(
        queue=queue,
        handlers={"dedup": handler},
        enable_scheduler=False,
        session_factory=queue._session_factory,
    )
    processed = await worker.process_once()
    assert processed == 1
    handler.assert_called_once()
    db = queue._session_factory()
    from app.models import GovernanceJob
    import uuid

    row = db.query(GovernanceJob).filter_by(id=uuid.UUID(job_id)).one()
    assert row.status == GovernanceJobStatus.done
    db.close()


@pytest.mark.asyncio
async def test_failed_job_requeues_until_max_attempts(queue):
    from app.workers import governance_worker as gw

    queue.enqueue("dedup")
    calls = {"n": 0}

    def boom(**kwargs):
        calls["n"] += 1
        raise RuntimeError("fail")

    worker = gw.GovernanceWorker(
        queue=queue,
        handlers={"dedup": boom},
        max_attempts=2,
        enable_scheduler=False,
        session_factory=queue._session_factory,
    )
    await worker.process_once()
    db = queue._session_factory()
    from app.models import GovernanceJob

    row = db.query(GovernanceJob).one()
    assert row.status == GovernanceJobStatus.queued
    assert row.attempts == 1
    db.close()

    await worker.process_once()
    db = queue._session_factory()
    row = db.query(GovernanceJob).one()
    assert row.status == GovernanceJobStatus.failed
    db.close()
