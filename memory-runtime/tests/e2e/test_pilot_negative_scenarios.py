from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.pilot_negative_scenarios import run_pilot_negative_scenarios
from app.workers.runner import WorkerRunner


def test_pilot_negative_scenarios() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "pilot_negative_scenarios.db")
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = f"sqlite+pysqlite:///{db_path}"
        os.environ["MEMORY_RUNTIME_AUTO_CREATE_TABLES"] = "true"
        os.environ["MEMORY_RUNTIME_ENV"] = "test"
        get_settings.cache_clear()
        reset_database_caches()
        Base.metadata.create_all(bind=get_engine())

        client = TestClient(create_app())
        artifact_root = Path(temp_dir) / "pilot_traces"
        with patch("app.pilot_artifacts.ARTIFACT_ROOT", artifact_root):
            report = run_pilot_negative_scenarios(
                client,
                namespace_suffix="pytest-negative",
                artifact_run_name="pytest-negative",
                job_drainer=lambda: WorkerRunner.run_pending_jobs(),
                poll_seconds=0.0,
                max_wait_seconds=0.1,
            )

        assert report["total"] == 3
        assert report["passed"] == 3
        assert report["failed"] == 0
        assert report["artifact_dir"]
        assert (artifact_root / "pilot-negative-scenarios" / "pytest-negative" / "manifest.json").exists()

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
