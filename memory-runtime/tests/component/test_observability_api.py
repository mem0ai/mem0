import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.telemetry.metrics import reset_metrics
from app.workers.runner import WorkerRunner


class ObservabilityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "observability.db")
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
                "name": "cluster:metrics:shared",
                "mode": "shared",
                "source_systems": ["openclaw", "bunkerai"],
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

    def test_metrics_endpoint_exposes_prometheus_counters_and_job_gauges(self) -> None:
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_metrics_1",
                "source_system": "openclaw",
                "event_type": "architecture_decision",
                "space_hint": "project-space",
                "messages": [
                    {"role": "assistant", "content": "Metrics should expose recall and job counters."}
                ],
            },
        )
        self.client.post(
            "/v1/recall",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_metrics_1",
                "query": "What do metrics need to expose?",
                "context_budget_tokens": 500,
            },
        )
        WorkerRunner.run_pending_jobs()
        WorkerRunner.run_pending_jobs()

        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-type"],
            "text/plain; version=0.0.4; charset=utf-8",
        )
        body = response.text
        self.assertIn("# HELP memory_runtime_recall_requests_total", body)
        self.assertIn("memory_runtime_recall_requests_total 1", body)
        self.assertIn("memory_runtime_jobs_processed_total 2", body)
        self.assertIn('memory_runtime_job_status{status="completed"} 2', body)
        self.assertIn('memory_runtime_job_status_by_type{job_type="memory_consolidation",status="completed"} 1', body)
        self.assertIn('memory_runtime_job_status_by_type{job_type="memory_decay",status="completed"} 1', body)

    def test_observability_stats_endpoint_returns_metrics_and_job_breakdown(self) -> None:
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_metrics_2",
                "source_system": "openclaw",
                "event_type": "conversation_turn",
                "messages": [
                    {"role": "user", "content": "Track observability state for this run."}
                ],
            },
        )

        response = self.client.get("/v1/observability/stats")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("metrics", payload)
        self.assertIn("jobs", payload)
        self.assertEqual(payload["metrics"]["recall_requests_total"], 0)
        self.assertEqual(payload["jobs"]["by_status"]["pending"], 1)
        self.assertEqual(payload["jobs"]["by_type"]["memory_consolidation"]["pending"], 1)
