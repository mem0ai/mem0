import os
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app


class EventsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "events.db")
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
                "source_system": "openclaw",
            },
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

    def test_event_ingestion_creates_memory_event_and_episode(self) -> None:
        response = self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_123",
                "source_system": "openclaw",
                "event_type": "conversation_turn",
                "messages": [
                    {"role": "user", "content": "  Continue   the   plan  "},
                    {"role": "assistant", "content": " I updated the architecture notes. "},
                ],
                "metadata": {"project_id": "mem-runtime"},
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertIsNotNone(payload["episode_id"])
        self.assertEqual(payload["session_id"], "run_123")
        self.assertEqual(payload["project_id"], "mem-runtime")
        self.assertEqual(
            payload["payload_json"]["messages"],
            [
                {"role": "user", "content": "Continue the plan"},
                {"role": "assistant", "content": "I updated the architecture notes."},
            ],
        )

        with get_engine().connect() as connection:
            events_count = connection.execute(text("SELECT COUNT(*) FROM memory_events")).scalar_one()
            episodes_count = connection.execute(text("SELECT COUNT(*) FROM episodes")).scalar_one()

        self.assertEqual(events_count, 1)
        self.assertEqual(episodes_count, 1)
