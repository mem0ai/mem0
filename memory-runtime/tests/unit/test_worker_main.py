import unittest
from pathlib import Path
from unittest.mock import patch

from app.workers import main as worker_main


class WorkerMainTests(unittest.TestCase):
    @patch("app.workers.main.init_database")
    @patch("app.workers.main.WorkerRunner.run_pending_jobs", return_value=3)
    def test_run_once_initializes_database_and_processes_jobs(self, run_pending_jobs, init_database) -> None:
        processed = worker_main.run_once()

        self.assertEqual(processed, 3)
        init_database.assert_called_once()
        run_pending_jobs.assert_called_once()

    @patch("app.workers.main.time.sleep")
    @patch("app.workers.main.init_database")
    @patch("app.workers.main.WorkerRunner.run_pending_jobs", side_effect=[2, 0])
    def test_run_forever_honors_poll_interval_and_max_cycles(self, run_pending_jobs, init_database, sleep) -> None:
        processed = worker_main.run_forever(poll_seconds=0.25, max_cycles=2)

        self.assertEqual(processed, 2)
        init_database.assert_called_once()
        self.assertEqual(run_pending_jobs.call_count, 2)
        sleep.assert_called_once_with(0.25)

    @patch("app.workers.main.time.sleep")
    @patch("app.workers.main.init_database", side_effect=[RuntimeError("db down"), None])
    def test_initialize_database_with_retry_retries_until_success(self, init_database, sleep) -> None:
        worker_main.initialize_database_with_retry(poll_seconds=0.5, max_attempts=3)

        self.assertEqual(init_database.call_count, 2)
        sleep.assert_called_once_with(0.5)

    @patch("app.workers.main.time.sleep")
    @patch("app.workers.main.init_database", side_effect=RuntimeError("db down"))
    def test_initialize_database_with_retry_raises_after_max_attempts(self, init_database, sleep) -> None:
        with self.assertRaises(RuntimeError):
            worker_main.initialize_database_with_retry(poll_seconds=0.5, max_attempts=2)

        self.assertEqual(init_database.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    @patch("app.workers.main.run_once", return_value=1)
    def test_main_once_returns_zero(self, run_once) -> None:
        exit_code = worker_main.main(["--once"])

        self.assertEqual(exit_code, 0)
        run_once.assert_called_once()

    @patch("app.workers.main.HEARTBEAT_PATH", new=Path("/tmp/memory_runtime_worker_heartbeat_test"))
    def test_touch_heartbeat_writes_file(self) -> None:
        try:
            worker_main.HEARTBEAT_PATH.unlink(missing_ok=True)
            worker_main.touch_heartbeat()

            self.assertTrue(worker_main.HEARTBEAT_PATH.exists())
        finally:
            worker_main.HEARTBEAT_PATH.unlink(missing_ok=True)
