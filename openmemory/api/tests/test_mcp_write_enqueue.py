"""Tests for the non-blocking MCP write tool ``add_memories`` (task_07 / ADR-004).

``add_memories`` no longer extracts synchronously: it validates the input,
enqueues a :class:`WriteJob` and returns an immediate ack ``{"status":
"queued", "job_id": ...}``. The slow LLM extraction is done out of band by the
worker (task_06), so the memory client must NOT be touched on this path.

Covered:
- a valid call enqueues exactly one job and returns the queued ack;
- the enqueued job carries the resolved hostname (attribution, task_04) and the
  originating client_name;
- a missing/blank ``project`` returns a descriptive error and enqueues nothing;
- a blank ``text`` returns a descriptive error and enqueues nothing;
- the LLM/memory client is never invoked on the request path;
- integration: an ``add_memories`` call lands a row the worker can consume.
"""

import json
import os
import uuid
from unittest.mock import MagicMock, patch

# Dummy key before importing modules that may build a client lazily.
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import mcp_server
from app.mcp_server import add_memories
from app.models import WriteAuditLog
from app.models import WriteQueueJob as WriteQueueModel
from app.models import WriteQueueStatus
from app.mcp_server import DEFAULT_CLIENT_NAME
from app.utils.identity import DEFAULT_HOSTNAME
from app.utils.write_queue import WriteQueue


def _audit_factory():
    """In-memory sqlite sessionmaker with just the write_audit_logs table."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    WriteAuditLog.__table__.create(bind=engine, checkfirst=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# A fixed but realistic UUID (contains hex letters so SQLite keeps TEXT affinity;
# an all-numeric value would be coerced to a float on read-back).
FAKE_JOB_ID = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"


class _FakeQueue:
    """Records enqueued jobs; returns a deterministic (valid UUID) job id."""

    def __init__(self):
        self.jobs = []

    def enqueue(self, job):
        self.jobs.append(job)
        return FAKE_JOB_ID


@pytest.fixture
def fake_queue():
    q = _FakeQueue()
    # Also redirect the audit write to an isolated in-memory DB so unit tests do
    # not touch the real application database.
    with patch.object(mcp_server, "write_queue", q), \
            patch.object(mcp_server, "SessionLocal", _audit_factory()):
        yield q


def _set_ctx(uid="maqA", client="cursor"):
    mcp_server.user_id_var.set(uid)
    mcp_server.client_name_var.set(client)


# --------------------------------------------------------------------------- #
# Enqueue + ack
# --------------------------------------------------------------------------- #
class TestEnqueueAck:
    @pytest.mark.asyncio
    async def test_valid_call_enqueues_and_acks(self, fake_queue):
        _set_ctx()
        out = await add_memories("remember X", project="alpha")
        data = json.loads(out)

        assert data["status"] == "queued"
        assert data["job_id"] == FAKE_JOB_ID
        assert len(fake_queue.jobs) == 1

    @pytest.mark.asyncio
    async def test_job_carries_hostname_and_client(self, fake_queue):
        _set_ctx(uid="maqA", client="cursor")
        await add_memories("remember X", project="alpha")
        job = fake_queue.jobs[0]

        assert job.text == "remember X"
        assert job.project == "alpha"
        assert job.hostname == "maqA"       # attribution (task_04)
        assert job.client_name == "cursor"  # originating client

    @pytest.mark.asyncio
    async def test_project_is_trimmed(self, fake_queue):
        _set_ctx()
        await add_memories("x", project="  alpha  ")
        assert fake_queue.jobs[0].project == "alpha"

    @pytest.mark.asyncio
    async def test_missing_hostname_uses_default(self, fake_queue):
        # No user_id in context -> attribution falls back to the sentinel.
        mcp_server.user_id_var.set("")
        mcp_server.client_name_var.set("cursor")
        await add_memories("x", project="alpha")
        assert fake_queue.jobs[0].hostname == DEFAULT_HOSTNAME

    @pytest.mark.asyncio
    async def test_missing_client_name_uses_default(self, fake_queue):
        # No client_name in context -> falls back to the sentinel.
        mcp_server.user_id_var.set("maqA")
        mcp_server.client_name_var.set("")
        await add_memories("x", project="alpha")
        assert fake_queue.jobs[0].client_name == DEFAULT_CLIENT_NAME


# --------------------------------------------------------------------------- #
# Validation (no enqueue on bad input)
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.asyncio
    async def test_missing_project_errors_without_enqueue(self, fake_queue):
        _set_ctx()
        out = await add_memories("remember X", project="")
        assert "project not provided" in out
        assert fake_queue.jobs == []

    @pytest.mark.asyncio
    async def test_blank_project_errors_without_enqueue(self, fake_queue):
        _set_ctx()
        out = await add_memories("remember X", project="   ")
        assert "project not provided" in out
        assert fake_queue.jobs == []

    @pytest.mark.asyncio
    async def test_blank_text_errors_without_enqueue(self, fake_queue):
        _set_ctx()
        out = await add_memories("   ", project="alpha")
        assert "text not provided" in out
        assert fake_queue.jobs == []


# --------------------------------------------------------------------------- #
# No LLM on the request path
# --------------------------------------------------------------------------- #
class TestNoLlmOnRequestPath:
    @pytest.mark.asyncio
    async def test_memory_client_not_invoked(self, fake_queue):
        _set_ctx()
        client = MagicMock()
        with patch.object(mcp_server, "get_memory_client_safe", return_value=client):
            await add_memories("remember X", project="alpha")
        # The slow extraction must not run on the request path.
        client.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_failure_is_reported(self, fake_queue):
        _set_ctx()
        fake_queue.enqueue = MagicMock(side_effect=RuntimeError("db gone"))
        out = await add_memories("remember X", project="alpha")
        assert "Error enqueuing memory write" in out


# --------------------------------------------------------------------------- #
# Integration: enqueue lands a row the worker can consume
# --------------------------------------------------------------------------- #
class TestIntegrationWithQueue:
    @pytest.mark.asyncio
    async def test_add_memories_lands_consumable_row(self, tmp_path):
        db_path = str(tmp_path / "enqueue_it.db")
        engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )
        WriteQueueModel.__table__.create(bind=engine, checkfirst=True)
        WriteAuditLog.__table__.create(bind=engine, checkfirst=True)
        factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        real_queue = WriteQueue(session_factory=factory)

        with patch.object(mcp_server, "write_queue", real_queue), \
                patch.object(mcp_server, "SessionLocal", factory):
            _set_ctx(uid="maqA", client="cursor")
            out = await add_memories("remember X", project="alpha")

        job_id = json.loads(out)["job_id"]

        # The job is persisted as queued and dequeuable (worker-consumable).
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            assert row is not None
            assert row.status == WriteQueueStatus.queued
            assert row.project == "alpha"
            assert row.hostname == "maqA"
            assert row.client_name == "cursor"
        finally:
            db.close()

        dequeued = real_queue.dequeue(limit=1)
        assert len(dequeued) == 1
        assert dequeued[0].text == "remember X"

        # A durable audit row was recorded with the hostname attribution.
        db = factory()
        try:
            audit = db.query(WriteAuditLog).filter(
                WriteAuditLog.job_id == uuid.UUID(job_id)
            ).first()
            assert audit is not None
            assert audit.hostname == "maqA"
            assert audit.project == "alpha"
            assert audit.client_name == "cursor"
            assert audit.action == "enqueue"
        finally:
            db.close()
        engine.dispose()


# --------------------------------------------------------------------------- #
# Durable write audit (task_04 / ADR-003)
# --------------------------------------------------------------------------- #
class TestWriteAudit:
    @pytest.mark.asyncio
    async def test_enqueue_records_audit_with_hostname(self, fake_queue):
        _set_ctx(uid="maqZ", client="claude")
        out = await add_memories("remember X", project="alpha")
        job_id = json.loads(out)["job_id"]

        db = mcp_server.SessionLocal()
        try:
            audit = db.query(WriteAuditLog).filter(
                WriteAuditLog.job_id == uuid.UUID(job_id)
            ).first()
            assert audit is not None
            assert audit.hostname == "maqZ"        # attribution (task_04)
            assert audit.project == "alpha"
            assert audit.client_name == "claude"
        finally:
            db.close()

    @pytest.mark.asyncio
    async def test_invalid_input_records_no_audit(self, fake_queue):
        _set_ctx()
        await add_memories("remember X", project="")  # invalid -> no enqueue

        db = mcp_server.SessionLocal()
        try:
            assert db.query(WriteAuditLog).count() == 0
        finally:
            db.close()
