import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.quality_eval import load_scenarios, run_quality_eval


class QualityEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "quality_eval.db")
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
                "name": "eval:memory-runtime",
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

        self._event(
            session_id="eval_run_baseline",
            event_type="conversation_turn",
            space_hint="project-space",
            content="The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
        )
        self._event(
            session_id="eval_run_baseline",
            event_type="architecture_decision",
            space_hint="project-space",
            content="We decided to keep the memory runtime Python-first architecture for v1.",
        )
        self._event(
            session_id="eval_run_baseline",
            event_type="policy_update",
            space_hint="agent-core",
            content="Always produce concise architecture summaries before implementation details.",
        )
        self._event(
            session_id="eval_run_active",
            event_type="conversation_turn",
            space_hint="session-space",
            content="In this session I need to draft the pilot acceptance checklist.",
        )
        self._event(
            session_id="eval_run_old",
            event_type="conversation_turn",
            space_hint="project-space",
            content="This old deprecated deployment note should not be recalled for active work.",
        )
        self._event(
            session_id="eval_run_old",
            event_type="conversation_turn",
            space_hint="session-space",
            content="Also book flights for the conference next month.",
        )
        self._event(
            session_id="eval_run_old",
            event_type="conversation_turn",
            space_hint="project-space",
            content="This is only a temporary scratch note and should not dominate recall.",
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

    def _event(self, *, session_id: str, event_type: str, space_hint: str, content: str) -> None:
        response = self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": session_id,
                "source_system": "openclaw",
                "event_type": event_type,
                "space_hint": space_hint,
                "messages": [{"role": "assistant", "content": content}],
            },
        )
        self.assertEqual(response.status_code, 201)

    def test_run_quality_eval_passes_golden_recall_scenarios(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "evals"
            / "recall_quality_scenarios.json"
        )
        scenarios = load_scenarios(fixture_path)
        materialized = json.loads(
            json.dumps(scenarios)
            .replace("EVAL_NAMESPACE_ID", self.namespace_id)
            .replace("EVAL_AGENT_ID", self.agent_id)
        )

        report = run_quality_eval(self.client, scenarios=materialized)

        self.assertEqual(report["total"], 3)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["passed"], 3)
        self.assertTrue(all(result["passed"] for result in report["results"]))
