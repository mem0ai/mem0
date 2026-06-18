"""Tests for worker env config, embedded gate, and SKIP LOCKED dequeue (tasks 02-03)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import uuid
from unittest.mock import MagicMock


from app.workers.write_worker import (
    DEFAULT_MAX_CONCURRENCY,
    worker_from_env,
)


class TestWorkerFromEnv:
    def test_max_concurrency_from_env(self, monkeypatch):
        monkeypatch.setenv("WRITE_WORKER_MAX_CONCURRENCY", "7")
        worker = worker_from_env()
        assert worker._max_concurrency == 7

    def test_defaults_when_env_missing(self, monkeypatch):
        for key in (
            "WRITE_WORKER_MAX_CONCURRENCY",
            "WRITE_WORKER_BATCH_SIZE",
            "WRITE_WORKER_IDLE_SLEEP",
            "WRITE_WORKER_MAX_ATTEMPTS",
        ):
            monkeypatch.delenv(key, raising=False)
        worker = worker_from_env()
        assert worker._max_concurrency == DEFAULT_MAX_CONCURRENCY


class TestEmbeddedWorkerGate:
    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("RUN_EMBEDDED_WORKER", raising=False)
        from app.workers.write_worker import embedded_worker_enabled

        assert embedded_worker_enabled() is True

    def test_disabled_when_false(self, monkeypatch):
        monkeypatch.setenv("RUN_EMBEDDED_WORKER", "false")
        from app.workers.write_worker import embedded_worker_enabled

        assert embedded_worker_enabled() is False


class TestDequeueSkipLocked:
    def test_postgresql_query_uses_skip_locked(self, db_path=None):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models import WriteQueueJob as WriteQueueModel
        from app.utils.write_queue import WriteQueue

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        WriteQueueModel.__table__.create(bind=engine)
        factory = sessionmaker(bind=engine)
        queue = WriteQueue(session_factory=factory)

        from app.utils.write_queue import WriteJob

        job_id = queue.enqueue(
            WriteJob(
                id=str(uuid.uuid4()),
                project="p",
                hostname="h",
                client_name="c",
                text="t",
                created_at="",
            )
        )
        jobs = queue.dequeue(limit=1)
        assert jobs[0].id == job_id

    def test_postgresql_branch_calls_with_for_update(self):
        from app.utils.write_queue import WriteQueue

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.limit.return_value.all.return_value = []

        mock_bind = MagicMock()
        mock_bind.url = "postgresql://u:p@h/db"
        mock_db.get_bind.return_value = mock_bind

        queue = WriteQueue(session_factory=lambda: mock_db)
        queue.dequeue(limit=1)

        mock_query.with_for_update.assert_called_once_with(skip_locked=True)
