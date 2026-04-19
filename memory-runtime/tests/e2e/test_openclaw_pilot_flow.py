import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.workers.runner import WorkerRunner


class OpenClawPilotFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "pilot_flow.db")
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

    def test_openclaw_pilot_continuity_flow(self) -> None:
        bootstrap = self.client.post(
            "/v1/adapters/openclaw/bootstrap",
            json={
                "namespace_name": "pilot:alice",
                "agent_name": "primary",
                "external_ref": "alice",
            },
        )

        self.assertEqual(bootstrap.status_code, 200)
        scope = bootstrap.json()
        namespace_id = scope["namespace_id"]
        agent_id = scope["agent_id"]

        durable_fact = self.client.post(
            "/v1/adapters/openclaw/events",
            json={
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "event_type": "architecture_decision",
                "space_hint": "project-space",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "The OpenClaw pilot should use memory-runtime with Postgres, Redis, and a dedicated memory worker.",
                    }
                ],
            },
        )
        self.assertEqual(durable_fact.status_code, 201)

        current_session = self.client.post(
            "/v1/adapters/openclaw/events",
            json={
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "session_id": "run_pilot_001",
                "event_type": "conversation_turn",
                "space_hint": "session-space",
                "messages": [
                    {
                        "role": "user",
                        "content": "Next I need a runbook and acceptance checklist for the OpenClaw MVP pilot.",
                    }
                ],
            },
        )
        self.assertEqual(current_session.status_code, 201)

        processed = WorkerRunner.run_pending_jobs()
        self.assertGreaterEqual(processed, 2)

        next_session_recall = self.client.post(
            "/v1/adapters/openclaw/recall",
            json={
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "session_id": "run_pilot_002",
                "query": "What stack and operational setup were chosen for the OpenClaw pilot?",
                "context_budget_tokens": 1000,
            },
        )

        self.assertEqual(next_session_recall.status_code, 200)
        brief = next_session_recall.json()["brief"]
        self.assertTrue(
            any(
                "Postgres, Redis, and a dedicated memory worker" in item
                for item in brief["prior_decisions"] + brief["active_project_context"]
            )
        )

        session_search = self.client.post(
            "/v1/adapters/openclaw/search",
            json={
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "session_id": "run_pilot_001",
                "query": "runbook acceptance checklist",
                "limit": 5,
            },
        )
        self.assertEqual(session_search.status_code, 200)
        session_results = session_search.json()["results"]
        self.assertTrue(
            any("runbook and acceptance checklist" in item["memory"] for item in session_results)
        )

        long_term_list = self.client.get(
            f"/v1/adapters/openclaw/memories?namespace_id={namespace_id}&agent_id={agent_id}"
        )
        self.assertEqual(long_term_list.status_code, 200)
        long_term_results = long_term_list.json()["results"]
        self.assertTrue(
            any("dedicated memory worker" in item["memory"] for item in long_term_results)
        )
