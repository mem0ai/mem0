"""Tests for the persistent write queue (task_05).

Covers the WriteQueue lifecycle (enqueue/dequeue/mark_done/mark_failed/depth)
against a temporary on-disk SQLite database, plus a persistence test that opens
a brand-new engine/connection to the same file to simulate a process restart.
"""

import os

# Set dummy keys before importing app modules that initialize clients.
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import WriteQueue as WriteQueueModel
from app.models import WriteQueueStatus
from app.utils.write_queue import SqlWriteQueue, WriteJob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Path to a temporary on-disk SQLite file (durable across connections)."""
    return str(tmp_path / "write_queue_test.db")


def _make_factory(db_path):
    """Create an engine + sessionmaker bound to a real sqlite file and the
    write_queue schema. Returns (engine, sessionmaker)."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    # Only create the write_queue table to avoid pulling unrelated FKs.
    WriteQueueModel.__table__.create(bind=engine, checkfirst=True)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, factory


@pytest.fixture
def queue(db_path):
    """A SqlWriteQueue backed by a temporary sqlite file."""
    engine, factory = _make_factory(db_path)
    yield SqlWriteQueue(session_factory=factory)
    engine.dispose()


def _job(text="hello world", project="proj-a", hostname="host-1",
         client_name="cursor"):
    return WriteJob(
        id=str(uuid.uuid4()),
        project=project,
        hostname=hostname,
        client_name=client_name,
        text=text,
        created_at="",
    )


# ---------------------------------------------------------------------------
# enqueue
# ---------------------------------------------------------------------------

class TestEnqueue:
    def test_enqueue_creates_queued_and_returns_job_id(self, queue, db_path):
        job_id = queue.enqueue(_job())

        assert job_id
        # job_id is a valid UUID string
        uuid.UUID(job_id)

        # Row persisted with status queued
        _, factory = _make_factory(db_path)
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            assert row is not None
            assert row.status == WriteQueueStatus.queued
            assert row.text == "hello world"
            assert row.project == "proj-a"
            assert row.error is None
        finally:
            db.close()


# ---------------------------------------------------------------------------
# dequeue
# ---------------------------------------------------------------------------

class TestDequeue:
    def test_dequeue_returns_queued_and_marks_processing(self, queue, db_path):
        job_id = queue.enqueue(_job(text="t1"))

        jobs = queue.dequeue(limit=1)

        assert len(jobs) == 1
        assert jobs[0].id == job_id
        assert jobs[0].text == "t1"

        # Status is now processing
        _, factory = _make_factory(db_path)
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            assert row.status == WriteQueueStatus.processing
        finally:
            db.close()

    def test_dequeue_respects_limit_and_fifo(self, queue):
        id1 = queue.enqueue(_job(text="first"))
        id2 = queue.enqueue(_job(text="second"))
        queue.enqueue(_job(text="third"))

        jobs = queue.dequeue(limit=2)
        assert [j.id for j in jobs] == [id1, id2]

        # A second dequeue only returns still-queued items
        remaining = queue.dequeue(limit=10)
        assert len(remaining) == 1
        assert remaining[0].text == "third"

    def test_dequeue_empty_returns_empty_list(self, queue):
        assert queue.dequeue() == []


# ---------------------------------------------------------------------------
# mark_done / mark_failed
# ---------------------------------------------------------------------------

class TestStatusTransitions:
    def test_mark_done(self, queue, db_path):
        job_id = queue.enqueue(_job())
        queue.dequeue(limit=1)

        queue.mark_done(job_id)

        _, factory = _make_factory(db_path)
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            assert row.status == WriteQueueStatus.done
            assert row.error is None
        finally:
            db.close()

    def test_mark_failed_records_error(self, queue, db_path):
        job_id = queue.enqueue(_job())
        queue.dequeue(limit=1)

        queue.mark_failed(job_id, "llm timeout")

        _, factory = _make_factory(db_path)
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            assert row.status == WriteQueueStatus.failed
            assert row.error == "llm timeout"
        finally:
            db.close()

    def test_mark_status_unknown_id_is_noop(self, queue):
        # Should not raise for an unknown id.
        queue.mark_done(str(uuid.uuid4()))
        queue.mark_failed(str(uuid.uuid4()), "x")


# ---------------------------------------------------------------------------
# depth
# ---------------------------------------------------------------------------

class TestDepth:
    def test_depth_counts_pending(self, queue):
        assert queue.depth() == 0

        queue.enqueue(_job(text="a"))
        queue.enqueue(_job(text="b"))
        assert queue.depth() == 2

        # Dequeued (processing) jobs still count as pending.
        jobs = queue.dequeue(limit=1)
        assert queue.depth() == 2

        # Completed/failed jobs no longer count.
        queue.mark_done(jobs[0].id)
        assert queue.depth() == 1


# ---------------------------------------------------------------------------
# persistence across "restart"
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_jobs_survive_fresh_connection(self, db_path):
        # First "process": enqueue some jobs, then drop everything.
        engine1, factory1 = _make_factory(db_path)
        q1 = SqlWriteQueue(session_factory=factory1)
        id1 = q1.enqueue(_job(text="persist-me"))
        q1.enqueue(_job(text="and-me"))
        engine1.dispose()
        del q1, factory1, engine1

        # Second "process": brand-new engine/connection to the same file.
        engine2, factory2 = _make_factory(db_path)
        q2 = SqlWriteQueue(session_factory=factory2)
        try:
            assert q2.depth() == 2

            jobs = q2.dequeue(limit=10)
            ids = {j.id for j in jobs}
            assert id1 in ids
            texts = {j.text for j in jobs}
            assert texts == {"persist-me", "and-me"}
        finally:
            engine2.dispose()
