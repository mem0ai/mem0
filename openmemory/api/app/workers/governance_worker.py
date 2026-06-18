"""Governance worker — processor + scheduler (tasks 05–06 / ADR-002)."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable, Dict, Optional

from app.database import SessionLocal
from app.governance.consolidation import run_consolidate_job
from app.governance.dedup import run_dedup_job
from app.governance.purge import run_purge_job
from app.governance.quality_eval import run_quality_eval_job
from app.governance.ttl_prune import run_ttl_prune_job
from app.models import GovernanceJobType, GovernanceSchedule, Project
from app.utils.governance_policy import GLOBAL_SCOPE, resolve_policy
from app.utils.governance_queue import GovernanceJob, governance_queue
from app.utils.metrics import (
    GOVERNANCE_JOB_ERRORS,
    GOVERNANCE_JOB_LATENCY,
    GOVERNANCE_JOB_QUEUE_DEPTH,
)
from app.utils.logging_context import job_id_var

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 2
DEFAULT_BATCH_SIZE = 4
DEFAULT_IDLE_SLEEP = 2.0
DEFAULT_SCHEDULER_SLEEP = 60.0
DEFAULT_MAX_ATTEMPTS = 3

SCHEDULE_INTERVALS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}


Handler = Callable[..., int]


class GovernanceWorker:
    def __init__(
        self,
        queue=None,
        *,
        handlers: Optional[Dict[str, Handler]] = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        idle_sleep: float = DEFAULT_IDLE_SLEEP,
        scheduler_sleep: float = DEFAULT_SCHEDULER_SLEEP,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        enable_scheduler: bool = True,
        session_factory=SessionLocal,
    ):
        self._queue = queue or governance_queue
        self._handlers = handlers or _default_handlers()
        self._max_concurrency = max_concurrency
        self._batch_size = batch_size
        self._idle_sleep = idle_sleep
        self._scheduler_sleep = scheduler_sleep
        self._max_attempts = max_attempts
        self._enable_scheduler = enable_scheduler
        self._session_factory = session_factory
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._stopped = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._scheduler_task: Optional[asyncio.Task] = None

    def register_handler(self, job_type: str, handler: Handler) -> None:
        self._handlers[job_type] = handler

    async def process_once(self) -> int:
        jobs = self._queue.dequeue(limit=self._batch_size)
        if not jobs:
            return 0
        await asyncio.gather(*(self._process_job(job) for job in jobs))
        return len(jobs)

    async def _process_job(self, job: GovernanceJob) -> None:
        token = job_id_var.set(job.id)
        started = time.perf_counter()
        try:
            async with self._semaphore:
                handler = self._handlers.get(job.job_type)
                if handler is None:
                    self._queue.mark_failed(job.id, f"unknown job_type {job.job_type}", job.attempts + 1)
                    GOVERNANCE_JOB_ERRORS.labels(job_type=job.job_type).inc()
                    return
                try:
                    limit = int((job.payload or {}).get("limit", 500))
                    await asyncio.to_thread(
                        handler,
                        project=job.project,
                        job_id=job.id,
                        limit=limit,
                    )
                    self._queue.mark_done(job.id)
                except Exception as exc:  # noqa: BLE001
                    GOVERNANCE_JOB_ERRORS.labels(job_type=job.job_type).inc()
                    attempts = job.attempts + 1
                    if attempts >= self._max_attempts:
                        self._queue.mark_failed(job.id, str(exc), attempts)
                    else:
                        self._queue.requeue(job.id, str(exc), attempts)
        finally:
            GOVERNANCE_JOB_LATENCY.labels(job_type=job.job_type).observe(
                time.perf_counter() - started
            )
            job_id_var.reset(token)

    def schedule_due_jobs(self) -> int:
        if not self._in_off_peak_window():
            return 0
        db = self._session_factory()
        enqueued = 0
        try:
            scopes = [GLOBAL_SCOPE] + [p.name for p in db.query(Project).all()]
            for scope in scopes:
                project = None if scope == GLOBAL_SCOPE else scope
                policy = resolve_policy(project or "", session_factory=self._session_factory)
                for job_type, cadence in (policy.schedules or {}).items():
                    if job_type == "quality_eval":
                        gtype = "consolidate"  # reuse enum bucket; handled separately below
                    else:
                        try:
                            gtype = job_type
                            GovernanceJobType(gtype)
                        except ValueError:
                            continue
                    if not self._is_due(db, gtype, scope, cadence):
                        continue
                    if gtype == "consolidate" and not policy.consolidation_enabled:
                        continue
                    self._queue.enqueue(gtype, project=project, payload={"scheduled": True})
                    self._mark_scheduled(db, gtype, scope)
                    enqueued += 1
                if scope != GLOBAL_SCOPE and policy.consolidation_enabled:
                    if self._is_due(db, "quality_eval", scope, policy.schedules.get("quality_eval", "weekly")):
                        self._queue.enqueue(
                            "consolidate",
                            project=project,
                            payload={"quality_eval": True},
                        )
                        self._mark_scheduled(db, "quality_eval", scope)
                        enqueued += 1
            if enqueued:
                db.commit()
            return enqueued
        finally:
            db.close()

    @staticmethod
    def _in_off_peak_window() -> bool:
        hour = datetime.now(UTC).hour
        policy = resolve_policy("")
        return hour in policy.off_peak_hours_utc

    @staticmethod
    def _interval(cadence: str) -> timedelta:
        return SCHEDULE_INTERVALS.get(cadence, timedelta(days=1))

    def _is_due(self, db, job_type: str, scope: str, cadence: str) -> bool:
        try:
            enum_type = GovernanceJobType(job_type if job_type != "quality_eval" else "consolidate")
        except ValueError:
            return False
        row = (
            db.query(GovernanceSchedule)
            .filter(
                GovernanceSchedule.job_type == enum_type,
                GovernanceSchedule.scope == scope,
            )
            .first()
        )
        if row is None or row.last_run_at is None:
            return True
        return datetime.now(UTC) - row.last_run_at.replace(tzinfo=UTC) >= self._interval(cadence)

    def _mark_scheduled(self, db, job_type: str, scope: str) -> None:
        enum_type = GovernanceJobType(job_type if job_type != "quality_eval" else "consolidate")
        row = (
            db.query(GovernanceSchedule)
            .filter(
                GovernanceSchedule.job_type == enum_type,
                GovernanceSchedule.scope == scope,
            )
            .first()
        )
        now = datetime.now(UTC)
        if row is None:
            db.add(GovernanceSchedule(job_type=enum_type, scope=scope, last_run_at=now))
        else:
            row.last_run_at = now

    async def _scheduler_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                self.schedule_due_jobs()
                for jt in GovernanceJobType:
                    GOVERNANCE_JOB_QUEUE_DEPTH.labels(job_type=jt.value).set(
                        self._queue.depth(jt.value)
                    )
            except Exception:  # noqa: BLE001
                logger.exception("governance scheduler pass failed")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self._scheduler_sleep)
            except asyncio.TimeoutError:
                pass

    async def run(self) -> None:
        recovered = self._queue.recover_stale_processing()
        if recovered:
            logger.info("recovered %s stale governance jobs", recovered)
        if self._enable_scheduler and self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        while not self._stopped.is_set():
            try:
                processed = await self.process_once()
            except Exception:  # noqa: BLE001
                logger.exception("governance worker pass failed")
                processed = 0
            if processed == 0:
                try:
                    await asyncio.wait_for(self._stopped.wait(), timeout=self._idle_sleep)
                except asyncio.TimeoutError:
                    pass

    def start(self) -> asyncio.Task:
        self._stopped.clear()
        self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        self._stopped.set()
        if self._scheduler_task is not None:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


def _quality_handler(*, project, job_id, limit=500) -> int:
    run_quality_eval_job(project=project)
    return 1


def _dispatching_consolidate(*, project, job_id, limit=500, payload=None) -> int:
    return run_consolidate_job(project=project, job_id=job_id, limit=limit)


def _default_handlers() -> Dict[str, Handler]:
    return {
        "dedup": run_dedup_job,
        "ttl_prune": run_ttl_prune_job,
        "consolidate": run_consolidate_job,
        "purge": run_purge_job,
    }


def worker_from_env() -> GovernanceWorker:
    return GovernanceWorker(
        max_concurrency=_env_int("GOVERNANCE_WORKER_MAX_CONCURRENCY", DEFAULT_MAX_CONCURRENCY),
        batch_size=_env_int("GOVERNANCE_WORKER_BATCH_SIZE", DEFAULT_BATCH_SIZE),
        idle_sleep=_env_float("GOVERNANCE_WORKER_IDLE_SLEEP", DEFAULT_IDLE_SLEEP),
        scheduler_sleep=_env_float("GOVERNANCE_SCHEDULER_SLEEP", DEFAULT_SCHEDULER_SLEEP),
        max_attempts=_env_int("GOVERNANCE_WORKER_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
        enable_scheduler=_env_bool("GOVERNANCE_ENABLE_SCHEDULER", True),
    )


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else float(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


async def _main() -> None:
    worker = worker_from_env()
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _request_stop() -> None:
        stop_event.set()

    import signal

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _request_stop())

    worker.start()
    await stop_event.wait()
    await worker.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())


if __name__ == "__main__":
    main()
