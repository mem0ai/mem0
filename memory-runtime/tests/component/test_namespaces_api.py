import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app


class NamespaceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "runtime.db")
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

    def test_create_and_get_shared_namespace(self) -> None:
        create_response = self.client.post(
            "/v1/namespaces",
            json={
                "name": "cluster:project-alpha:shared",
                "mode": "shared",
                "source_systems": ["openclaw", "bunkerai"],
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["mode"], "shared")
        self.assertEqual(len(created["spaces"]), 1)
        self.assertEqual(created["spaces"][0]["space_type"], "shared-space")

        get_response = self.client.get(f"/v1/namespaces/{created['id']}")
        self.assertEqual(get_response.status_code, 200)
        fetched = get_response.json()
        self.assertEqual(fetched["name"], "cluster:project-alpha:shared")
        self.assertEqual(fetched["source_systems"], ["openclaw", "bunkerai"])

    def test_create_agent_provisions_default_spaces(self) -> None:
        namespace_response = self.client.post(
            "/v1/namespaces",
            json={
                "name": "openclaw:agent:planner",
                "mode": "isolated",
                "source_systems": ["openclaw"],
            },
        )
        namespace_id = namespace_response.json()["id"]

        response = self.client.post(
            f"/v1/namespaces/{namespace_id}/agents",
            json={
                "name": "planner",
                "source_system": "openclaw",
                "external_ref": "planner-1",
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["name"], "planner")
        self.assertEqual(
            sorted(space["space_type"] for space in payload["spaces"]),
            ["agent-core", "project-space", "session-space"],
        )
