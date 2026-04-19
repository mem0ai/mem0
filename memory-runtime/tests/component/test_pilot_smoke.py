import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.pilot_smoke import run_pilot_smoke
from app.workers.runner import WorkerRunner


class PilotSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "pilot_smoke.db")
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

    def test_run_pilot_smoke_returns_successful_report(self) -> None:
        report = run_pilot_smoke(
            self.client,
            namespace_suffix="component-test",
            poll_seconds=0.0,
            max_wait_seconds=0.1,
            job_drainer=WorkerRunner.run_pending_jobs,
        )

        self.assertTrue(report["namespace_id"])
        self.assertTrue(report["agent_id"])
        self.assertTrue(any("dedicated memory worker" in item for item in report["recall_prior_decisions"]))
        self.assertTrue(any("acceptance checklist" in item for item in report["session_search_results"]))
        self.assertEqual(report["jobs_by_status"]["pending"], 0)
        self.assertGreaterEqual(report["jobs_by_status"]["completed"], 2)
