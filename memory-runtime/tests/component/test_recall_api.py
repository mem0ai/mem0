import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app


class RecallApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "recall.db")
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
            json={
                "name": "planner",
                "source_system": "openclaw"
            },
        )
        self.agent_id = agent_response.json()["id"]

        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_123",
                "source_system": "openclaw",
                "event_type": "conversation_turn",
                "messages": [
                    {"role": "user", "content": "Continue the Phase D recall MVP work for the memory runtime."}
                ]
            },
        )
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_100",
                "source_system": "openclaw",
                "event_type": "conversation_turn",
                "space_hint": "project-space",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "The memory runtime uses Postgres, Redis, and pgvector as the baseline stack."
                    }
                ]
            },
        )
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_101",
                "source_system": "openclaw",
                "event_type": "architecture_decision",
                "space_hint": "project-space",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "We decided to keep the memory runtime Python-first for v1 and postpone any Go rewrite."
                    }
                ]
            },
        )
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_102",
                "source_system": "openclaw",
                "event_type": "policy_update",
                "space_hint": "agent-core",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Always produce concise architecture summaries before implementation details."
                    }
                ]
            },
        )

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

    def test_recall_returns_structured_memory_brief(self) -> None:
        response = self.client.post(
            "/v1/recall",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_123",
                "query": "What architecture decisions already exist about the memory runtime?",
                "context_budget_tokens": 1200
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("brief", payload)
        self.assertIn("trace", payload)
        self.assertIn("prior_decisions", payload["brief"])
        self.assertIn("active_project_context", payload["brief"])
        self.assertIn("standing_procedures", payload["brief"])
        self.assertIn("recent_session_carryover", payload["brief"])
        self.assertTrue(
            any("Python-first" in item for item in payload["brief"]["prior_decisions"])
        )
        self.assertTrue(
            any("Postgres, Redis, and pgvector" in item for item in payload["brief"]["active_project_context"])
        )
        self.assertTrue(
            any("concise architecture summaries" in item for item in payload["brief"]["standing_procedures"])
        )
        self.assertTrue(
            any("Phase D recall MVP" in item for item in payload["brief"]["recent_session_carryover"])
        )
