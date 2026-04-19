from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.continuity_benchmark import run_continuity_benchmark
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.workers.runner import WorkerRunner


class ContinuityBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "continuity_benchmark.db")
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = f"sqlite+pysqlite:///{self.db_path}"
        os.environ["MEMORY_RUNTIME_AUTO_CREATE_TABLES"] = "true"
        os.environ["MEMORY_RUNTIME_ENV"] = "test"
        get_settings.cache_clear()
        reset_database_caches()
        Base.metadata.create_all(bind=get_engine())
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        for key in (
            "MEMORY_RUNTIME_POSTGRES_DSN",
            "MEMORY_RUNTIME_AUTO_CREATE_TABLES",
            "MEMORY_RUNTIME_ENV",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()
        reset_database_caches()

    def test_continuity_benchmark_passes_golden_scenarios(self) -> None:
        report = run_continuity_benchmark(
            self.client,
            namespace_suffix="test-benchmark",
            job_drainer=WorkerRunner.run_pending_jobs,
            poll_seconds=0.01,
            max_wait_seconds=1.0,
        )

        self.assertEqual(report["total"], 3)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["passed"], 3)
        self.assertGreater(report["metrics"]["avg_selected_count"], 0.0)
        self.assertTrue(all(item["passed"] for item in report["results"]))
