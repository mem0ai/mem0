import unittest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


class HealthEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        get_settings.cache_clear()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_healthz_returns_service_status(self) -> None:
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "Agent Memory Runtime",
                "environment": "development",
            },
        )

    def test_root_exposes_docs_pointer(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["docs"], "/docs")
