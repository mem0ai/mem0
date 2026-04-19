from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, get_engine, get_session_factory, reset_database_caches
from app.repositories.agents import AgentRepository
from app.repositories.episodes import EpisodeRepository
from app.repositories.memory_events import MemoryEventRepository
from app.repositories.memory_spaces import MemorySpaceRepository
from app.repositories.namespaces import NamespaceRepository


class AdapterSharedRecallRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "adapter-shared-recall.db")
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = f"sqlite+pysqlite:///{self.db_path}"
        get_settings.cache_clear()
        reset_database_caches()
        Base.metadata.create_all(bind=get_engine())
        self.session: Session = get_session_factory()()

    def tearDown(self) -> None:
        self.session.close()
        self.temp_dir.cleanup()
        os.environ.pop("MEMORY_RUNTIME_POSTGRES_DSN", None)
        get_settings.cache_clear()
        reset_database_caches()

    def test_shared_space_is_visible_across_agents_but_agent_core_stays_private(self) -> None:
        namespaces = NamespaceRepository(self.session)
        agents = AgentRepository(self.session)
        spaces = MemorySpaceRepository(self.session)
        events = MemoryEventRepository(self.session)
        episodes = EpisodeRepository(self.session)

        namespace = namespaces.create(
            name="cluster:beta:shared",
            mode="shared",
            source_systems=["openclaw", "bunkerai"],
        )
        shared_space = spaces.create(
            namespace_id=namespace.id,
            space_type="shared-space",
            name="Shared Space",
        )
        openclaw_agent = agents.create(
            namespace_id=namespace.id,
            name="planner",
            source_system="openclaw",
        )
        bunker_agent = agents.create(
            namespace_id=namespace.id,
            name="researcher",
            source_system="bunkerai",
        )
        openclaw_core = spaces.create(
            namespace_id=namespace.id,
            agent_id=openclaw_agent.id,
            space_type="agent-core",
            name="Agent Core",
        )

        shared_event = events.create(
            namespace_id=namespace.id,
            agent_id=openclaw_agent.id,
            space_id=shared_space.id,
            session_id="run_1",
            project_id="cluster-beta",
            source_system="openclaw",
            event_type="architecture_decision",
            payload_json={"messages": [{"role": "assistant", "content": "Shared stack uses Postgres and Redis."}]},
            event_ts=datetime.now(timezone.utc),
            dedupe_key="shared-event",
        )
        private_event = events.create(
            namespace_id=namespace.id,
            agent_id=openclaw_agent.id,
            space_id=openclaw_core.id,
            session_id="run_2",
            project_id="cluster-beta",
            source_system="openclaw",
            event_type="policy_update",
            payload_json={"messages": [{"role": "assistant", "content": "OpenClaw private policy."}]},
            event_ts=datetime.now(timezone.utc),
            dedupe_key="private-event",
        )
        episodes.create(
            namespace_id=namespace.id,
            agent_id=openclaw_agent.id,
            space_id=shared_space.id,
            session_id="run_1",
            start_event_id=shared_event.id,
            end_event_id=shared_event.id,
            summary="architecture_decision: Shared stack uses Postgres and Redis.",
            raw_text="assistant: Shared stack uses Postgres and Redis.",
            token_count=7,
            importance_hint="high",
        )
        episodes.create(
            namespace_id=namespace.id,
            agent_id=openclaw_agent.id,
            space_id=openclaw_core.id,
            session_id="run_2",
            start_event_id=private_event.id,
            end_event_id=private_event.id,
            summary="policy_update: OpenClaw private policy.",
            raw_text="assistant: OpenClaw private policy.",
            token_count=4,
            importance_hint="normal",
        )
        self.session.commit()

        rows = episodes.list_for_recall(
            namespace_id=namespace.id,
            agent_id=bunker_agent.id,
            session_id=None,
            space_types=["shared-space", "agent-core"],
        )
        summaries = {episode.summary for episode, _space_type in rows}

        self.assertIn("architecture_decision: Shared stack uses Postgres and Redis.", summaries)
        self.assertNotIn("policy_update: OpenClaw private policy.", summaries)
