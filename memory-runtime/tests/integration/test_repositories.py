from __future__ import annotations

import os
import tempfile
import unittest

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, get_engine, get_session_factory, reset_database_caches
from app.models import Agent, MemorySpace, Namespace  # noqa: F401
from app.repositories.agents import AgentRepository
from app.repositories.memory_spaces import MemorySpaceRepository
from app.repositories.namespaces import NamespaceRepository


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "repo.db")
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

    def test_namespace_and_agent_repositories(self) -> None:
        namespaces = NamespaceRepository(self.session)
        agents = AgentRepository(self.session)
        spaces = MemorySpaceRepository(self.session)

        namespace = namespaces.create(
            name="cluster:alpha:shared",
            mode="shared",
            source_systems=["openclaw", "bunkerai"],
        )
        spaces.create(namespace_id=namespace.id, space_type="shared-space", name="Shared Space")
        agent = agents.create(
            namespace_id=namespace.id,
            name="researcher",
            source_system="bunkerai",
        )
        spaces.create(
            namespace_id=namespace.id,
            agent_id=agent.id,
            space_type="agent-core",
            name="Agent Core",
        )
        self.session.commit()

        found_namespace = namespaces.get_by_name("cluster:alpha:shared")
        found_agent = agents.get_by_name(namespace.id, "researcher")
        found_spaces = spaces.list_by_agent(namespace.id, agent.id)

        self.assertIsNotNone(found_namespace)
        self.assertIsNotNone(found_agent)
        self.assertEqual(len(found_spaces), 1)
        self.assertEqual(found_spaces[0].space_type, "agent-core")
