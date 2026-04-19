import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app


class AdaptersApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "adapters.db")
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
                "name": "cluster:alpha:shared",
                "mode": "shared",
                "source_systems": ["openclaw", "bunkerai"],
            },
        )
        self.namespace_id = namespace_response.json()["id"]

        openclaw_agent = self.client.post(
            f"/v1/namespaces/{self.namespace_id}/agents",
            json={
                "name": "planner",
                "source_system": "openclaw",
            },
        )
        self.openclaw_agent_id = openclaw_agent.json()["id"]

        bunker_agent = self.client.post(
            f"/v1/namespaces/{self.namespace_id}/agents",
            json={
                "name": "researcher",
                "source_system": "bunkerai",
            },
        )
        self.bunkerai_agent_id = bunker_agent.json()["id"]

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

    def test_openclaw_adapter_event_contract_wraps_ingestion_response(self) -> None:
        response = self.client.post(
            "/v1/adapters/openclaw/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.openclaw_agent_id,
                "session_id": "run_oc_1",
                "event_type": "conversation_turn",
                "messages": [
                    {"role": "user", "content": "Persist the cluster coordination note."},
                ],
                "metadata": {"project_id": "cluster-alpha"},
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["adapter"], "openclaw")
        self.assertEqual(payload["source_system"], "openclaw")
        self.assertEqual(payload["event"]["source_system"], "openclaw")
        self.assertEqual(payload["event"]["agent_id"], self.openclaw_agent_id)
        self.assertEqual(payload["event"]["project_id"], "cluster-alpha")
        self.assertIsNotNone(payload["event"]["episode_id"])

    def test_bunkerai_adapter_recall_contract_wraps_recall_response(self) -> None:
        self.client.post(
            "/v1/adapters/bunkerai/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.bunkerai_agent_id,
                "session_id": "run_ba_1",
                "event_type": "conversation_turn",
                "messages": [
                    {"role": "assistant", "content": "BunkerAI tracks the release checklist for the memory runtime."},
                ],
            },
        )

        response = self.client.post(
            "/v1/adapters/bunkerai/recall",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.bunkerai_agent_id,
                "session_id": "run_ba_1",
                "query": "What is BunkerAI tracking for the memory runtime?",
                "context_budget_tokens": 600,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["adapter"], "bunkerai")
        self.assertEqual(payload["source_system"], "bunkerai")
        self.assertIn("brief", payload)
        self.assertIn("trace", payload)
        self.assertIn("recent_session_carryover", payload["brief"])
        self.assertGreaterEqual(payload["trace"]["candidate_count"], 1)

    def test_shared_namespace_supports_cross_agent_shared_memory_without_private_leakage(self) -> None:
        self.client.post(
            "/v1/adapters/openclaw/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.openclaw_agent_id,
                "session_id": "run_oc_2",
                "event_type": "architecture_decision",
                "space_hint": "shared-space",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "The shared deployment stack for the memory runtime is Postgres, Redis, and pgvector.",
                    }
                ],
            },
        )
        self.client.post(
            "/v1/adapters/openclaw/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.openclaw_agent_id,
                "session_id": "run_oc_3",
                "event_type": "policy_update",
                "space_hint": "agent-core",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Only the OpenClaw planner should use the bulletless status format.",
                    }
                ],
            },
        )

        response = self.client.post(
            "/v1/adapters/bunkerai/recall",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.bunkerai_agent_id,
                "session_id": "run_ba_2",
                "query": "What shared deployment stack do we use for the memory runtime?",
                "context_budget_tokens": 800,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        flattened_brief = " ".join(
            item
            for section in payload["brief"].values()
            for item in section
        )

        self.assertIn("Postgres, Redis, and pgvector", flattened_brief)
        self.assertNotIn("bulletless status format", flattened_brief)
        self.assertIn("shared-space", payload["trace"]["selected_space_types"])
