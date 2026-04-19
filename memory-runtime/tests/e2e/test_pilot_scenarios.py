from __future__ import annotations

import os
import tempfile

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.pilot_scenarios import run_pilot_scenarios
from app.workers.runner import WorkerRunner


def test_pilot_scenario_subset() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "pilot_scenarios.db")
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = f"sqlite+pysqlite:///{db_path}"
        os.environ["MEMORY_RUNTIME_AUTO_CREATE_TABLES"] = "true"
        os.environ["MEMORY_RUNTIME_ENV"] = "test"
        get_settings.cache_clear()
        reset_database_caches()
        Base.metadata.create_all(bind=get_engine())

        client = TestClient(create_app())
        report = run_pilot_scenarios(
            client,
            namespace_suffix="pytest",
            job_drainer=lambda: WorkerRunner.run_pending_jobs(),
            poll_seconds=0.0,
            max_wait_seconds=0.1,
        )

        assert report["total"] == 5
        assert report["passed"] == 5
        assert report["failed"] == 0
        assert report["metrics"]["avg_selected_count"] > 0

        for result in report["results"]:
            assert result["passed"] is True

        for key in (
            "MEMORY_RUNTIME_POSTGRES_DSN",
            "MEMORY_RUNTIME_AUTO_CREATE_TABLES",
            "MEMORY_RUNTIME_ENV",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()
        reset_database_caches()
