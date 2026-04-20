from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.preflight import run_preflight


def test_preflight_fails_cleanly_when_worker_does_not_process_jobs() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "failure-preflight.db")
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = f"sqlite+pysqlite:///{db_path}"
        os.environ["MEMORY_RUNTIME_AUTO_CREATE_TABLES"] = "true"
        os.environ["MEMORY_RUNTIME_ENV"] = "test"
        get_settings.cache_clear()
        reset_database_caches()
        Base.metadata.create_all(bind=get_engine())

        client = TestClient(create_app())
        report = run_preflight(
            client,
            namespace_suffix="worker-down",
            job_drainer=None,
            poll_seconds=0.0,
            max_wait_seconds=0.0,
        )

        assert report["status"] == "fail"
        assert report["checks"]["healthz_ok"] is True
        assert report["checks"]["metrics_exposed"] is True
        assert report["checks"]["observability_available"] is True
        assert report["checks"]["worker_processed_job"] is False
        assert report["jobs_by_status"]["pending"] == 1

        for key in (
            "MEMORY_RUNTIME_POSTGRES_DSN",
            "MEMORY_RUNTIME_AUTO_CREATE_TABLES",
            "MEMORY_RUNTIME_ENV",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()
        reset_database_caches()


def test_observability_surfaces_stalled_running_job_in_degraded_state() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "failure-stalled.db")
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = f"sqlite+pysqlite:///{db_path}"
        os.environ["MEMORY_RUNTIME_AUTO_CREATE_TABLES"] = "true"
        os.environ["MEMORY_RUNTIME_ENV"] = "test"
        get_settings.cache_clear()
        reset_database_caches()
        Base.metadata.create_all(bind=get_engine())

        client = TestClient(create_app())
        namespace = client.post(
            "/v1/namespaces",
            json={
                "name": "cluster:failure-mode:shared",
                "mode": "shared",
                "source_systems": ["openclaw", "bunkerai"],
            },
        ).json()
        agent = client.post(
            f"/v1/namespaces/{namespace['id']}/agents",
            json={"name": "planner", "source_system": "openclaw"},
        ).json()

        response = client.post(
            "/v1/events",
            json={
                "namespace_id": namespace["id"],
                "agent_id": agent["id"],
                "session_id": "run_failure_1",
                "source_system": "openclaw",
                "event_type": "conversation_turn",
                "messages": [{"role": "user", "content": "Create a job that will appear stalled."}],
            },
        )
        assert response.status_code == 201

        stale_started_at = (datetime.now(timezone.utc) - timedelta(seconds=180)).isoformat()
        with get_engine().begin() as connection:
            connection.execute(
                text("UPDATE jobs SET status = 'running', started_at = :started_at"),
                {"started_at": stale_started_at},
            )

        stats = client.get("/v1/observability/stats")

        assert stats.status_code == 200
        payload = stats.json()
        assert payload["jobs"]["by_status"]["running"] == 1
        assert payload["jobs"]["stalled_running_count"] == 1
        assert payload["jobs"]["oldest_pending_age_seconds"] is None

        for key in (
            "MEMORY_RUNTIME_POSTGRES_DSN",
            "MEMORY_RUNTIME_AUTO_CREATE_TABLES",
            "MEMORY_RUNTIME_ENV",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()
        reset_database_caches()
