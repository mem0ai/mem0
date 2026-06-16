"""Asynchronous write worker (task_06).

Consumes the persistent write queue (``app.utils.write_queue.write_queue``) and
runs the slow LLM extraction/persistence out of band so that the MCP
``add_memories`` tool can return an immediate ack (ADR-004). For each job the
worker:

1. dequeues ``queued`` jobs (the queue marks them ``processing``);
2. calls the mem0 client ``add(text, project=…, user_id=hostname, metadata=…)``
   — ``user_id`` carries the hostname purely for attribution (ADR-003);
3. upserts the project catalog on the first write of each project (ADR-002),
   idempotently;
4. marks the job ``done`` on success; on failure it retries (re-queues the job
   with an incremented ``attempts`` count) until ``max_attempts`` is reached,
   then marks it terminally ``failed`` recording the error — failed jobs are
   never lost, they stay in the table.

Concurrency against the local LLM is bounded by an ``asyncio.Semaphore`` so a
burst of writes never fires more than ``max_concurrency`` simultaneous
inferences, protecting the Ollama instance from overload.

Testability: the loop is split into :meth:`WriteWorker.process_once` (one
dequeue+process pass) so tests can drive a single iteration without an infinite
loop. :meth:`WriteWorker.run` is the long-running loop used at app startup.
"""

import asyncio
import logging
from typing import Callable, Optional

from app.utils.projects import upsert_project as _default_upsert_project
from app.utils.write_queue import WriteJob
from app.utils.write_queue import write_queue as _default_write_queue

logger = logging.getLogger(__name__)

# Default bound on concurrent LLM inferences. Kept small so the local LLM is not
# saturated by a burst of queued writes; overridable via the constructor.
DEFAULT_MAX_CONCURRENCY = 2

# How many times a job is attempted before it is marked terminally ``failed``.
# On a failed attempt the job is re-queued (retentativa) until this ceiling is
# reached; jobs are never lost regardless (ADR-004).
DEFAULT_MAX_ATTEMPTS = 3

# How many jobs to pull from the queue per pass and how long to idle (seconds)
# when the queue is empty before polling again.
DEFAULT_BATCH_SIZE = 8
DEFAULT_IDLE_SLEEP = 1.0


def _default_client_provider():
    """Lazily import the memory client accessor.

    Imported lazily from ``app.utils.memory`` (the infrastructure layer) so that
    importing this module never triggers client/Ollama initialization.
    """
    from app.utils.memory import get_memory_client_safe

    return get_memory_client_safe()


class WriteWorker:
    """Background consumer of the write queue.

    Args:
        queue: The write queue to consume (defaults to the shared singleton).
        client_provider: Zero-arg callable returning a mem0 client (or ``None``
            when the LLM/memory backend is unavailable). Injected for testing.
        upsert_project: Callable ``(name, hostname) -> None`` registering a
            project in the catalog (idempotent).
        max_concurrency: Maximum number of concurrent ``add`` calls.
        batch_size: Maximum number of jobs dequeued per pass.
        idle_sleep: Seconds to sleep when the queue is empty.
    """

    def __init__(
        self,
        queue=None,
        client_provider: Optional[Callable] = None,
        upsert_project: Optional[Callable] = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        idle_sleep: float = DEFAULT_IDLE_SLEEP,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ):
        self._queue = queue if queue is not None else _default_write_queue
        self._client_provider = client_provider or _default_client_provider
        self._upsert_project = upsert_project or _default_upsert_project
        self._max_concurrency = max(1, int(max_concurrency))
        self._batch_size = max(1, int(batch_size))
        self._idle_sleep = idle_sleep
        self._max_attempts = max(1, int(max_attempts))

        self._semaphore = asyncio.Semaphore(self._max_concurrency)
        # Projects already cataloged in this process; avoids a redundant DB
        # round-trip after the first write of a project (the catalog upsert is
        # idempotent regardless, this is just a cheap short-circuit).
        self._cataloged_projects: set = set()

        self._task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()

    # --------------------------------------------------------------------- #
    # Single-pass processing (testable seam)
    # --------------------------------------------------------------------- #
    async def process_once(self) -> int:
        """Dequeue and process one batch of jobs.

        Returns the number of jobs that were dequeued in this pass. Returns 0
        when the queue is empty. Jobs in the batch are processed concurrently,
        bounded by the configured semaphore.
        """
        jobs = self._queue.dequeue(limit=self._batch_size)
        if not jobs:
            return 0

        await asyncio.gather(*(self._process_job(job) for job in jobs))
        return len(jobs)

    async def _process_job(self, job: WriteJob) -> None:
        """Process a single job: extract/persist, catalog, mark done/failed.

        On failure (including the LLM/memory backend being unavailable) the job
        is retried — re-queued with an incremented ``attempts`` count — until the
        configured ceiling is reached, at which point it is marked terminally
        ``failed``. Either way the job is never lost: it stays in the table.
        """
        async with self._semaphore:
            try:
                client = self._client_provider()
                if client is None:
                    # LLM/memory backend unavailable: do not lose the job.
                    raise RuntimeError(
                        "memory client unavailable (LLM/backend down)"
                    )

                await self._run_add(client, job)
                self._catalog_project(job)
                self._queue.mark_done(job.id)
            except Exception as e:  # noqa: BLE001 - background isolation
                self._handle_failure(job, e)

    def _handle_failure(self, job: WriteJob, error: Exception) -> None:
        """Re-queue the job for another attempt, or fail it terminally.

        Bounded retentativa (ADR-004): a transient failure (e.g. the LLM being
        momentarily down) re-queues the job so a later pass reprocesses it; once
        ``max_attempts`` is reached the job is marked ``failed`` and stops being
        retried. A failure to record the transition is swallowed so the worker
        loop never dies.
        """
        attempts = job.attempts + 1
        will_retry = attempts < self._max_attempts
        logger.warning(
            "write job attempt %s/%s failed job_id=%s project=%s hostname=%s "
            "(%s): %s",
            attempts,
            self._max_attempts,
            job.id,
            job.project,
            job.hostname,
            "will retry" if will_retry else "giving up",
            error,
        )
        try:
            if will_retry:
                self._queue.requeue(job.id, str(error), attempts)
            else:
                self._queue.mark_failed(job.id, str(error), attempts)
        except Exception:  # noqa: BLE001
            logger.exception(
                "could not record failure transition for job %s", job.id
            )

    async def _run_add(self, client, job: WriteJob):
        """Invoke the mem0 client ``add``.

        ``user_id`` carries the hostname for attribution only (ADR-003); the
        project scope travels in ``project`` + ``metadata`` so reads filter by
        project. Supports both async and sync clients (the OpenMemory default
        client is sync, so it is run in a thread to avoid blocking the loop).
        """
        kwargs = dict(
            user_id=job.hostname,
            project=job.project,
            metadata={
                "project": job.project,
                "hostname": job.hostname,
                "source_app": "openmemory",
                "mcp_client": job.client_name,
            },
        )
        add = client.add
        if asyncio.iscoroutinefunction(add):
            return await add(job.text, **kwargs)

        # Call it; if the client returned a coroutine/awaitable (e.g. an async
        # client wrapped so ``iscoroutinefunction`` does not detect it), await
        # the result. Otherwise it is a sync client (the OpenMemory default) —
        # offload to a thread so the LLM call does not block the event loop.
        # We probe sync-ness with iscoroutinefunction first to avoid running a
        # blocking sync ``add`` on the event loop thread.
        result = await asyncio.to_thread(add, job.text, **kwargs)
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            return await result
        return result

    def _catalog_project(self, job: WriteJob) -> None:
        """Upsert the project catalog on the first write of each project."""
        if job.project in self._cataloged_projects:
            return
        self._upsert_project(job.project, job.hostname)
        self._cataloged_projects.add(job.project)

    # --------------------------------------------------------------------- #
    # Long-running loop + lifecycle
    # --------------------------------------------------------------------- #
    async def run(self) -> None:
        """Run the consume loop until :meth:`stop` is requested."""
        logger.info(
            "write worker started (max_concurrency=%s, batch_size=%s)",
            self._max_concurrency,
            self._batch_size,
        )
        # NOTE: the stop event is (re)cleared in start() *before* the task is
        # scheduled — never here. Clearing it inside run() races with stop():
        # if stop() runs before this coroutine body executes, it would wipe the
        # stop signal and the loop would never terminate (the task hangs).
        while not self._stopped.is_set():
            try:
                processed = await self.process_once()
            except Exception:  # noqa: BLE001 - never let the loop die
                logger.exception("write worker pass failed; continuing")
                processed = 0
            if processed == 0:
                # Idle: wait for the poll interval or an early stop signal.
                try:
                    await asyncio.wait_for(
                        self._stopped.wait(), timeout=self._idle_sleep
                    )
                except asyncio.TimeoutError:
                    pass
        logger.info("write worker stopped")

    def start(self) -> asyncio.Task:
        """Schedule :meth:`run` as a background task on the running loop."""
        if self._task is None or self._task.done():
            # Reset the stop signal here, before scheduling the task, so a
            # stop() issued right after start() cannot be erased by run().
            self._stopped.clear()
            self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        """Signal the loop to stop and await the background task."""
        self._stopped.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None


# Shared worker instance used by the application startup hook.
write_worker = WriteWorker()
