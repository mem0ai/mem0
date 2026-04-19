import os
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.telemetry.metrics import reset_metrics, snapshot_metrics
from app.main import create_app
from app.workers.runner import WorkerRunner


class LifecyclePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "lifecycle.db")
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = f"sqlite+pysqlite:///{self.db_path}"
        os.environ["MEMORY_RUNTIME_AUTO_CREATE_TABLES"] = "true"
        os.environ["MEMORY_RUNTIME_ENV"] = "test"
        get_settings.cache_clear()
        reset_database_caches()
        reset_metrics()
        Base.metadata.create_all(bind=get_engine())
        self.client = TestClient(create_app())

        namespace_response = self.client.post(
            "/v1/namespaces",
            json={
                "name": "openclaw:agent:planner",
                "mode": "isolated",
                "source_systems": ["openclaw"],
            },
        )
        self.namespace_id = namespace_response.json()["id"]
        agent_response = self.client.post(
            f"/v1/namespaces/{self.namespace_id}/agents",
            json={"name": "planner", "source_system": "openclaw"},
        )
        self.agent_id = agent_response.json()["id"]

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
        reset_metrics()

    def _create_project_memory(self) -> None:
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_123",
                "source_system": "openclaw",
                "event_type": "architecture_decision",
                "space_hint": "project-space",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "We chose Python-first architecture for the memory runtime."
                    }
                ],
            },
        )
        WorkerRunner.run_pending_jobs()

    def test_consolidation_enqueues_lifecycle_job(self) -> None:
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_123",
                "source_system": "openclaw",
                "event_type": "architecture_decision",
                "space_hint": "project-space",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "We chose Python-first architecture for the memory runtime."
                    }
                ],
            },
        )

        WorkerRunner.run_pending_jobs()

        with get_engine().connect() as connection:
            lifecycle_jobs = connection.execute(
                text("SELECT COUNT(*) FROM jobs WHERE job_type = 'memory_decay'")
            ).scalar_one()

        self.assertEqual(lifecycle_jobs, 1)

    def test_lifecycle_job_decays_active_project_memory_and_emits_metrics(self) -> None:
        self._create_project_memory()

        WorkerRunner.run_pending_jobs()

        with get_engine().connect() as connection:
            row = connection.execute(
                text("SELECT freshness_score, status FROM memory_units LIMIT 1")
            ).fetchone()
            audit_actions = connection.execute(
                text("SELECT action FROM audit_log ORDER BY created_at ASC")
            ).fetchall()

        self.assertIsNotNone(row)
        self.assertLess(row[0], 1.0)
        self.assertEqual(row[1], "active")
        self.assertIn("memory_unit_decayed", [action[0] for action in audit_actions])

        metrics = snapshot_metrics()
        self.assertEqual(metrics["lifecycle_decayed_total"], 1)

    def test_old_session_memory_is_archived_by_lifecycle_job(self) -> None:
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_session",
                "source_system": "openclaw",
                "event_type": "conversation_turn",
                "messages": [
                    {"role": "user", "content": "Remember this temporary detail for the current session"}
                ],
            },
        )
        WorkerRunner.run_pending_jobs()

        with get_engine().connect() as connection:
            connection.execute(
                text(
                    "UPDATE memory_units SET created_at = datetime('now', '-4 days'), updated_at = datetime('now', '-4 days')"
                )
            )
            connection.commit()

        WorkerRunner.run_pending_jobs()

        with get_engine().connect() as connection:
            row = connection.execute(text("SELECT status FROM memory_units LIMIT 1")).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "archived")
