import os
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.workers.runner import WorkerRunner


class ConsolidationPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "consolidation.db")
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = f"sqlite+pysqlite:///{self.db_path}"
        os.environ["MEMORY_RUNTIME_AUTO_CREATE_TABLES"] = "true"
        os.environ["MEMORY_RUNTIME_ENV"] = "test"
        get_settings.cache_clear()
        reset_database_caches()
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

    def test_event_ingestion_enqueues_consolidation_job(self) -> None:
        response = self.client.post(
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

        self.assertEqual(response.status_code, 201)

        with get_engine().connect() as connection:
            jobs_count = connection.execute(text("SELECT COUNT(*) FROM jobs")).scalar_one()
            job_type = connection.execute(text("SELECT job_type FROM jobs LIMIT 1")).scalar_one()

        self.assertEqual(jobs_count, 1)
        self.assertEqual(job_type, "memory_consolidation")

    def test_worker_creates_memory_unit_and_audit_log(self) -> None:
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

        processed = WorkerRunner.run_pending_jobs()

        self.assertEqual(processed, 1)
        with get_engine().connect() as connection:
            memory_units_count = connection.execute(text("SELECT COUNT(*) FROM memory_units")).scalar_one()
            audit_count = connection.execute(text("SELECT COUNT(*) FROM audit_log")).scalar_one()
            status = connection.execute(text("SELECT status FROM jobs LIMIT 1")).scalar_one()

        self.assertEqual(memory_units_count, 1)
        self.assertEqual(audit_count, 1)
        self.assertEqual(status, "completed")

    def test_worker_merges_duplicate_consolidation_into_existing_memory_unit(self) -> None:
        payload = {
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
        }
        self.client.post("/v1/events", json=payload)
        self.client.post("/v1/events", json=payload)

        processed = WorkerRunner.run_pending_jobs()

        self.assertEqual(processed, 2)
        with get_engine().connect() as connection:
            memory_units_count = connection.execute(text("SELECT COUNT(*) FROM memory_units")).scalar_one()
            audit_actions = connection.execute(
                text("SELECT action FROM audit_log ORDER BY created_at ASC")
            ).fetchall()

        self.assertEqual(memory_units_count, 1)
        self.assertEqual([row[0] for row in audit_actions], ["memory_unit_created", "memory_unit_merged"])

    def test_worker_merges_semantically_equivalent_decision_phrasings(self) -> None:
        first_payload = {
            "namespace_id": self.namespace_id,
            "agent_id": self.agent_id,
            "session_id": "run_123",
            "source_system": "openclaw",
            "event_type": "conversation_turn",
            "space_hint": "project-space",
            "messages": [
                {
                    "role": "assistant",
                    "content": "We decided to keep the memory runtime Python-first for v1.",
                }
            ],
        }
        second_payload = {
            **first_payload,
            "messages": [
                {
                    "role": "assistant",
                    "content": "Keep the memory runtime Python-first for v1.",
                }
            ],
        }
        self.client.post("/v1/events", json=first_payload)
        self.client.post("/v1/events", json=second_payload)

        processed = WorkerRunner.run_pending_jobs()

        self.assertEqual(processed, 2)
        with get_engine().connect() as connection:
            row = connection.execute(
                text("SELECT kind, COUNT(*) FROM memory_units GROUP BY kind")
            ).fetchone()
            audit_actions = connection.execute(
                text("SELECT action FROM audit_log ORDER BY created_at ASC")
            ).fetchall()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "decision")
        self.assertEqual(row[1], 1)
        self.assertEqual([item[0] for item in audit_actions], ["memory_unit_created", "memory_unit_merged"])

    def test_worker_supersedes_contradictory_fact_in_same_space(self) -> None:
        first_payload = {
            "namespace_id": self.namespace_id,
            "agent_id": self.agent_id,
            "session_id": "run_123",
            "source_system": "openclaw",
            "event_type": "conversation_turn",
            "space_hint": "project-space",
            "messages": [
                {
                    "role": "assistant",
                    "content": "We use Postgres as the primary database for memory-runtime.",
                }
            ],
        }
        second_payload = {
            **first_payload,
            "messages": [
                {
                    "role": "assistant",
                    "content": "We do not use Postgres as the primary database for memory-runtime.",
                }
            ],
        }
        self.client.post("/v1/events", json=first_payload)
        self.client.post("/v1/events", json=second_payload)

        processed = WorkerRunner.run_pending_jobs()

        self.assertEqual(processed, 2)
        with get_engine().connect() as connection:
            memory_rows = connection.execute(
                text(
                    "SELECT status, supersedes_memory_id, content FROM memory_units ORDER BY created_at ASC"
                )
            ).fetchall()
            audit_actions = connection.execute(
                text("SELECT action FROM audit_log ORDER BY created_at ASC")
            ).fetchall()

        self.assertEqual(len(memory_rows), 2)
        self.assertEqual(memory_rows[0][0], "superseded")
        self.assertIsNone(memory_rows[0][1])
        self.assertEqual(memory_rows[1][0], "active")
        self.assertIsNotNone(memory_rows[1][1])
        self.assertIn("do not use Postgres", memory_rows[1][2])
        self.assertEqual([item[0] for item in audit_actions], ["memory_unit_created", "memory_unit_superseded"])
