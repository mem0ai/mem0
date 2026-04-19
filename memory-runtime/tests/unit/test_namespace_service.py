import unittest
from unittest.mock import MagicMock

from app.schemas.namespace import AgentCreate, NamespaceCreate
from app.services.namespaces import NamespaceService


class NamespaceServiceTests(unittest.TestCase):
    def test_shared_namespace_creates_shared_space(self) -> None:
        session = MagicMock()
        service = NamespaceService(session)

        namespace = MagicMock()
        namespace.id = "ns-1"
        namespace.name = "cluster:alpha:shared"
        namespace.mode = "shared"
        namespace.source_systems = ["openclaw", "bunkerai"]
        namespace.status = "active"
        namespace.created_at = namespace.updated_at = "2026-04-19T00:00:00Z"
        namespace.spaces = []

        service.namespaces.get_by_name = MagicMock(return_value=None)
        service.namespaces.create = MagicMock(return_value=namespace)
        service.spaces.create = MagicMock()

        service.create_namespace(
            NamespaceCreate(
                name="cluster:alpha:shared",
                mode="shared",
                source_systems=["openclaw", "bunkerai"],
            )
        )

        service.spaces.create.assert_called_once()

    def test_create_agent_provisions_three_default_spaces(self) -> None:
        session = MagicMock()
        service = NamespaceService(session)

        namespace = MagicMock()
        namespace.id = "ns-1"
        agent = MagicMock()
        agent.id = "ag-1"
        agent.namespace_id = "ns-1"
        agent.external_ref = None
        agent.name = "planner"
        agent.source_system = "openclaw"
        agent.created_at = "2026-04-19T00:00:00Z"
        agent.spaces = []

        service.namespaces.get_by_id = MagicMock(return_value=namespace)
        service.agents.get_by_name = MagicMock(return_value=None)
        service.agents.create = MagicMock(return_value=agent)
        service.spaces.create = MagicMock()

        service.create_agent(
            "ns-1",
            AgentCreate(name="planner", source_system="openclaw"),
        )

        self.assertEqual(service.spaces.create.call_count, 3)
