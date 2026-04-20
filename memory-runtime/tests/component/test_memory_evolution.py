import os
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.workers.runner import WorkerRunner


class MemoryEvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "memory-evolution.db")
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
                "name": "openclaw:agent:evolution",
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

    def _post_event(self, *, event_type: str, content: str, space_hint: str, session_id: str) -> None:
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

    def test_memory_evolves_through_merge_supersede_and_archive_cycles(self) -> None:
        self._post_event(
            event_type="conversation_turn",
            space_hint="project-space",
            session_id="run_merge_a",
            content="We decided to keep the memory runtime Python-first for v1.",
        )
        self._post_event(
            event_type="conversation_turn",
            space_hint="project-space",
            session_id="run_merge_b",
            content="Keep the memory runtime Python-first for v1.",
        )
        self._post_event(
            event_type="conversation_turn",
            space_hint="project-space",
            session_id="run_fact_a",
            content="We use Postgres as the primary database for memory-runtime.",
        )
        self._post_event(
            event_type="conversation_turn",
            space_hint="project-space",
            session_id="run_fact_b",
            content="We do not use Postgres as the primary database for memory-runtime.",
        )

        processed = WorkerRunner.run_pending_jobs()
        self.assertEqual(processed, 4)
        processed = WorkerRunner.run_pending_jobs()
        self.assertEqual(processed, 4)

        self._post_event(
            event_type="conversation_turn",
            space_hint="session-space",
            session_id="run_session_temp",
            content="Temporary session note: prepare the migration checklist before the next handoff.",
        )
        processed = WorkerRunner.run_pending_jobs()
        self.assertEqual(processed, 1)

        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE memory_units
                    SET created_at = datetime('now', '-4 days'),
                        updated_at = datetime('now', '-4 days')
                    WHERE scope = 'short-term'
                    """
                )
            )

        processed = WorkerRunner.run_pending_jobs()
        self.assertEqual(processed, 1)

        with get_engine().connect() as connection:
            decision_rows = connection.execute(
                text(
                    """
                    SELECT kind, status, content
                    FROM memory_units
                    WHERE kind = 'decision'
                    ORDER BY created_at ASC
                    """
                )
            ).fetchall()
            fact_rows = connection.execute(
                text(
                    """
                    SELECT kind, status, content, supersedes_memory_id
                    FROM memory_units
                    WHERE content LIKE '%primary database for memory-runtime%'
                    ORDER BY created_at ASC
                    """
                )
            ).fetchall()
            session_rows = connection.execute(
                text(
                    """
                    SELECT kind, status, content
                    FROM memory_units
                    WHERE scope = 'short-term'
                    ORDER BY created_at ASC
                    """
                )
            ).fetchall()
            audit_actions = connection.execute(
                text("SELECT action FROM audit_log ORDER BY created_at ASC")
            ).fetchall()

        self.assertEqual(len(decision_rows), 1)
        self.assertEqual(decision_rows[0][0], "decision")
        self.assertEqual(decision_rows[0][1], "active")
        self.assertIn("Python-first", decision_rows[0][2])

        self.assertEqual(len(fact_rows), 2)
        self.assertEqual(fact_rows[0][1], "superseded")
        self.assertEqual(fact_rows[1][1], "active")
        self.assertIsNotNone(fact_rows[1][3])
        self.assertIn("do not use Postgres", fact_rows[1][2])

        self.assertEqual(len(session_rows), 1)
        self.assertEqual(session_rows[0][1], "archived")
        self.assertIn("migration checklist", session_rows[0][2])

        action_names = [row[0] for row in audit_actions]
        self.assertIn("memory_unit_created", action_names)
        self.assertIn("memory_unit_merged", action_names)
        self.assertIn("memory_unit_superseded", action_names)
        self.assertIn("memory_unit_archived", action_names)
