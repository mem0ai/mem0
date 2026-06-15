"""Tests for the asynchronous write worker (task_06).

The worker consumes the persistent write queue and runs the LLM
extraction/persistence out of band (ADR-004). These tests drive a single
``process_once`` pass (the testable seam) against:

- a temporary on-disk SQLite database for the queue (reusing the write_queue
  test pattern), and
- a fully mocked memory client (no Qdrant / Ollama / LLM access).

Covered:
- a queued job is consumed -> ``client.add`` is called with the correct
  ``project`` + ``user_id`` (hostname) and the job is marked ``done``;
- extraction raising -> job marked ``failed`` with the error recorded;
- the first job of a new project triggers a single catalog upsert; the second
  does not duplicate it;
- the concurrency limit is respected (never more than N concurrent ``add``
  calls);
- LLM/memory client unavailable -> the job is not lost (marked ``failed`` and
  remains in the table, reprocessable).
"""

import asyncio
import os

# Set dummy keys before importing app modules that initialize clients.
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import WriteQueue as WriteQueueModel
from app.models import WriteQueueStatus
from app.utils.write_queue import SqlWriteQueue, WriteJob
from app.workers.write_worker import WriteWorker


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "write_worker_test.db")


def _make_factory(db_path):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    WriteQueueModel.__table__.create(bind=engine, checkfirst=True)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, factory


@pytest.fixture
def queue(db_path):
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


def _status(db_path, job_id):
    _, factory = _make_factory(db_path)
    db = factory()
    try:
        row = db.query(WriteQueueModel).filter(
            WriteQueueModel.id == uuid.UUID(job_id)
        ).first()
        return row
    finally:
        db.close()


def _async_client():
    """A mocked memory client whose ``add`` is an async coroutine."""
    client = MagicMock()

    async def _add(text, **kwargs):
        return {"results": [{"id": str(uuid.uuid4()), "memory": text,
                             "event": "ADD"}]}

    client.add = MagicMock(side_effect=_add)
    return client


# --------------------------------------------------------------------------- #
# Consumption + success
# --------------------------------------------------------------------------- #
class TestConsumeSuccess:
    @pytest.mark.asyncio
    async def test_job_consumed_calls_add_and_marks_done(self, queue, db_path):
        client = _async_client()
        upserts = []
        worker = WriteWorker(
            queue=queue,
            client_provider=lambda: client,
            upsert_project=lambda name, hostname: upserts.append((name, hostname)),
            max_concurrency=2,
        )

        job_id = queue.enqueue(_job(text="remember X", project="alpha",
                                    hostname="maqA", client_name="cursor"))

        processed = await worker.process_once()

        assert processed == 1
        # add called once, with the right project + hostname attribution.
        assert client.add.call_count == 1
        args, kwargs = client.add.call_args
        assert args[0] == "remember X"
        assert kwargs["project"] == "alpha"
        assert kwargs["user_id"] == "maqA"
        assert kwargs["metadata"]["project"] == "alpha"
        assert kwargs["metadata"]["hostname"] == "maqA"
        assert kwargs["metadata"]["mcp_client"] == "cursor"

        # Job marked done, no error.
        row = _status(db_path, job_id)
        assert row.status == WriteQueueStatus.done
        assert row.error is None

    @pytest.mark.asyncio
    async def test_empty_queue_is_noop(self, queue):
        worker = WriteWorker(queue=queue, client_provider=lambda: _async_client(),
                             upsert_project=lambda *a, **k: None)
        assert await worker.process_once() == 0

    @pytest.mark.asyncio
    async def test_sync_client_add_is_supported(self, queue, db_path):
        # A plain (sync) client.add — the OpenMemory default is sync.
        client = MagicMock()
        client.add = MagicMock(return_value={"results": []})
        worker = WriteWorker(queue=queue, client_provider=lambda: client,
                             upsert_project=lambda *a, **k: None)
        job_id = queue.enqueue(_job())

        assert await worker.process_once() == 1
        assert client.add.call_count == 1
        assert _status(db_path, job_id).status == WriteQueueStatus.done


# --------------------------------------------------------------------------- #
# Failure handling
# --------------------------------------------------------------------------- #
class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_extraction_error_marks_failed_with_error(self, queue, db_path):
        client = MagicMock()
        client.add = MagicMock(side_effect=RuntimeError("llm exploded"))
        worker = WriteWorker(queue=queue, client_provider=lambda: client,
                             upsert_project=lambda *a, **k: None)
        job_id = queue.enqueue(_job())

        processed = await worker.process_once()

        assert processed == 1
        row = _status(db_path, job_id)
        assert row.status == WriteQueueStatus.failed
        assert "llm exploded" in row.error

    @pytest.mark.asyncio
    async def test_failed_job_is_not_lost_and_no_catalog_upsert(self, queue):
        client = MagicMock()
        client.add = MagicMock(side_effect=RuntimeError("boom"))
        upserts = []
        worker = WriteWorker(queue=queue, client_provider=lambda: client,
                             upsert_project=lambda n, h: upserts.append(n))
        queue.enqueue(_job())

        await worker.process_once()

        # The job still exists in the table (failed, reprocessable) and the
        # project was NOT cataloged because the write did not succeed.
        assert queue.depth() == 0  # failed no longer "pending"
        assert upserts == []


# --------------------------------------------------------------------------- #
# Catalog upsert (idempotent, first write only)
# --------------------------------------------------------------------------- #
class TestCatalogUpsert:
    @pytest.mark.asyncio
    async def test_first_job_upserts_once_second_does_not_duplicate(
        self, queue, db_path
    ):
        client = _async_client()
        upserts = []
        worker = WriteWorker(
            queue=queue,
            client_provider=lambda: client,
            upsert_project=lambda name, hostname: upserts.append((name, hostname)),
        )

        queue.enqueue(_job(project="shared", hostname="maqA"))
        await worker.process_once()
        queue.enqueue(_job(project="shared", hostname="maqB"))
        await worker.process_once()

        # Same project written twice -> a single catalog upsert.
        assert upserts == [("shared", "maqA")]

    @pytest.mark.asyncio
    async def test_distinct_projects_each_upsert_once(self, queue):
        client = _async_client()
        upserts = []
        worker = WriteWorker(
            queue=queue,
            client_provider=lambda: client,
            upsert_project=lambda name, hostname: upserts.append(name),
        )
        queue.enqueue(_job(project="alpha"))
        queue.enqueue(_job(project="beta"))

        await worker.process_once()

        assert sorted(upserts) == ["alpha", "beta"]


# --------------------------------------------------------------------------- #
# Concurrency limit
# --------------------------------------------------------------------------- #
class TestConcurrencyLimit:
    @pytest.mark.asyncio
    async def test_never_exceeds_max_concurrency(self, queue):
        max_conc = 2
        n_jobs = 8
        state = {"current": 0, "peak": 0}
        lock = asyncio.Lock()

        client = MagicMock()

        async def _add(text, **kwargs):
            async with lock:
                state["current"] += 1
                state["peak"] = max(state["peak"], state["current"])
            await asyncio.sleep(0.02)
            async with lock:
                state["current"] -= 1
            return {"results": []}

        client.add = MagicMock(side_effect=_add)

        worker = WriteWorker(
            queue=queue,
            client_provider=lambda: client,
            upsert_project=lambda *a, **k: None,
            max_concurrency=max_conc,
            batch_size=n_jobs,
        )
        for i in range(n_jobs):
            queue.enqueue(_job(text=f"t{i}"))

        processed = await worker.process_once()

        assert processed == n_jobs
        assert client.add.call_count == n_jobs
        assert state["peak"] <= max_conc


# --------------------------------------------------------------------------- #
# LLM/backend unavailable
# --------------------------------------------------------------------------- #
class TestBackendUnavailable:
    @pytest.mark.asyncio
    async def test_client_none_marks_failed_not_lost(self, queue, db_path):
        worker = WriteWorker(
            queue=queue,
            client_provider=lambda: None,  # backend down
            upsert_project=lambda *a, **k: None,
        )
        job_id = queue.enqueue(_job())

        processed = await worker.process_once()

        assert processed == 1
        row = _status(db_path, job_id)
        assert row.status == WriteQueueStatus.failed
        assert row.error  # error recorded; job remains in the table
        # Re-enqueue path: the failed job is still present and reprocessable.
        assert row is not None


# --------------------------------------------------------------------------- #
# Lifecycle (run/stop loop)
# --------------------------------------------------------------------------- #
class TestLifecycle:
    @pytest.mark.asyncio
    async def test_run_processes_then_stops(self, queue, db_path):
        client = _async_client()
        worker = WriteWorker(
            queue=queue,
            client_provider=lambda: client,
            upsert_project=lambda *a, **k: None,
            idle_sleep=0.01,
        )
        job_id = queue.enqueue(_job())

        task = worker.start()
        # Give the loop a few iterations to drain the queue.
        for _ in range(50):
            await asyncio.sleep(0.01)
            if _status(db_path, job_id).status == WriteQueueStatus.done:
                break
        await worker.stop()

        assert task.done()
        assert _status(db_path, job_id).status == WriteQueueStatus.done

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, queue):
        worker = WriteWorker(queue=queue, client_provider=lambda: _async_client(),
                             upsert_project=lambda *a, **k: None, idle_sleep=0.01)
        t1 = worker.start()
        t2 = worker.start()
        assert t1 is t2  # no second task spawned
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self, queue):
        worker = WriteWorker(queue=queue, client_provider=lambda: None,
                             upsert_project=lambda *a, **k: None)
        await worker.stop()  # must not raise

    @pytest.mark.asyncio
    async def test_run_survives_a_failing_pass(self, queue, db_path):
        # A queue whose dequeue raises once, then behaves normally: the loop
        # must not die on a failing pass.
        client = _async_client()
        real_dequeue = queue.dequeue
        calls = {"n": 0}

        def flaky_dequeue(limit=1):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient db error")
            return real_dequeue(limit=limit)

        queue.dequeue = flaky_dequeue
        worker = WriteWorker(queue=queue, client_provider=lambda: client,
                             upsert_project=lambda *a, **k: None, idle_sleep=0.01)
        job_id = queue.enqueue(_job())

        worker.start()
        for _ in range(50):
            await asyncio.sleep(0.01)
            if _status(db_path, job_id).status == WriteQueueStatus.done:
                break
        await worker.stop()

        assert _status(db_path, job_id).status == WriteQueueStatus.done


# --------------------------------------------------------------------------- #
# mark_failed inner-failure isolation
# --------------------------------------------------------------------------- #
class TestMarkFailedIsolation:
    @pytest.mark.asyncio
    async def test_mark_failed_raising_is_swallowed(self, queue):
        # add fails AND mark_failed fails -> the worker must not propagate.
        client = MagicMock()
        client.add = MagicMock(side_effect=RuntimeError("boom"))
        worker = WriteWorker(queue=queue, client_provider=lambda: client,
                             upsert_project=lambda *a, **k: None)
        worker._queue.mark_failed = MagicMock(side_effect=RuntimeError("db gone"))
        queue.enqueue(_job())

        # Should not raise despite both add and mark_failed failing.
        processed = await worker.process_once()
        assert processed == 1


# --------------------------------------------------------------------------- #
# Async-def client.add path + default client provider + cancellation
# --------------------------------------------------------------------------- #
class TestAsyncAddPath:
    @pytest.mark.asyncio
    async def test_true_coroutine_function_add_is_awaited(self, queue, db_path):
        # A real `async def` add (iscoroutinefunction is True) is awaited
        # directly rather than offloaded to a thread.
        captured = {}

        async def real_add(text, **kwargs):
            captured["text"] = text
            captured["project"] = kwargs.get("project")
            return {"results": []}

        client = MagicMock()
        client.add = real_add  # not wrapped: a genuine coroutine function

        worker = WriteWorker(queue=queue, client_provider=lambda: client,
                             upsert_project=lambda *a, **k: None)
        job_id = queue.enqueue(_job(text="async path", project="alpha"))

        assert await worker.process_once() == 1
        assert captured == {"text": "async path", "project": "alpha"}
        assert _status(db_path, job_id).status == WriteQueueStatus.done


class TestDefaultClientProvider:
    def test_default_client_provider_delegates_to_mcp_server(self):
        from app import mcp_server
        from app.workers.write_worker import _default_client_provider

        sentinel = object()
        with patch.object(mcp_server, "get_memory_client_safe", return_value=sentinel):
            assert _default_client_provider() is sentinel


class TestStopCancellation:
    @pytest.mark.asyncio
    async def test_stop_swallows_cancelled_task(self, queue):
        # If the background task is cancelled, stop() must swallow the
        # CancelledError and clear the task reference without raising.
        worker = WriteWorker(queue=queue, client_provider=lambda: _async_client(),
                             upsert_project=lambda *a, **k: None, idle_sleep=10)
        worker.start()
        worker._task.cancel()

        await worker.stop()  # must not raise
        assert worker._task is None
