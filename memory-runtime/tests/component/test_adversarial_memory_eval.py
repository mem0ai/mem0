from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.adversarial_eval import load_scenarios, run_adversarial_eval
from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.workers.runner import WorkerRunner


class AdversarialMemoryEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "adversarial_eval.db")
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
                "name": "eval:adversarial-memory",
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

    def test_adversarial_eval_passes_golden_scenarios(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "evals"
            / "adversarial_memory_scenarios.json"
        )

        report = run_adversarial_eval(
            self.client,
            engine=get_engine(),
            namespace_id=self.namespace_id,
            agent_id=self.agent_id,
            scenarios=load_scenarios(fixture_path),
            job_drainer=WorkerRunner.run_pending_jobs,
        )

        self.assertEqual(report["total"], 6)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["passed"], 6)
        self.assertEqual(report["metrics"]["false_accepts"], 0)
        self.assertEqual(report["metrics"]["false_rejects"], 0)
        self.assertGreater(report["metrics"]["rejection_rate"], 0.0)
        self.assertGreater(report["metrics"]["acceptance_rate"], 0.0)
        self.assertTrue(all(item["passed"] for item in report["results"]))
