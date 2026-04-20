import os
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.database import Base, get_engine, reset_database_caches
from app.main import create_app
from app.models.memory_unit import MemoryUnit
from app.telemetry.metrics import reset_metrics
from app.workers.runner import WorkerRunner

MCP_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def _jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }


def _initialize_payload(req_id: int = 1) -> dict:
    return _jsonrpc(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.1.0"},
        },
        req_id=req_id,
    )


class MCPApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "mcp.db")
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
                "name": "openclaw:mcp:planner",
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

        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_mcp_1",
                "source_system": "openclaw",
                "event_type": "architecture_decision",
                "space_hint": "project-space",
                "messages": [
                    {"role": "assistant", "content": "The runtime baseline uses Postgres, Redis, and pgvector."}
                ],
            },
        )
        self.client.post(
            "/v1/events",
            json={
                "namespace_id": self.namespace_id,
                "agent_id": self.agent_id,
                "session_id": "run_mcp_2",
                "source_system": "openclaw",
                "event_type": "policy_update",
                "space_hint": "agent-core",
                "messages": [
                    {"role": "assistant", "content": "Always summarize architecture decisions before detailed plans."}
                ],
            },
        )
        WorkerRunner.run_pending_jobs()
        WorkerRunner.run_pending_jobs()

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

    def _post_mcp(self, payload: dict, *, client_name: str = "openclaw", user_id: str = "alice"):
        return self.client.post(
            f"/mcp/{client_name}/http/{user_id}",
            json=payload,
            headers=MCP_HEADERS,
        )

    def test_initialize_returns_server_capabilities(self) -> None:
        response = self._post_mcp(_initialize_payload())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(payload["id"], 1)
        self.assertEqual(payload["result"]["protocolVersion"], "2025-03-26")
        self.assertIn("serverInfo", payload["result"])
        self.assertIn("capabilities", payload["result"])

    def test_tools_list_and_recall_flow_return_structured_content(self) -> None:
        self._post_mcp(_initialize_payload())
        tools_response = self._post_mcp(_jsonrpc("tools/list", req_id=2))
        tool_names = {tool["name"] for tool in tools_response.json()["result"]["tools"]}

        self.assertEqual(tools_response.status_code, 200)
        self.assertIn("memory.recall", tool_names)
        self.assertIn("memory.search", tool_names)
        self.assertIn("memory.list_spaces", tool_names)
        self.assertIn("memory.get_observability_snapshot", tool_names)
        self.assertIn("memory.get_memory_unit", tool_names)

        recall_response = self._post_mcp(
            _jsonrpc(
                "tools/call",
                {
                    "name": "memory.recall",
                    "arguments": {
                        "namespace_id": self.namespace_id,
                        "agent_id": self.agent_id,
                        "query": "What architecture context already exists for the memory runtime?",
                        "context_budget_tokens": 900,
                    },
                },
                req_id=3,
            )
        )
        recall_payload = recall_response.json()

        self.assertEqual(recall_response.status_code, 200)
        self.assertFalse(recall_payload["result"]["isError"])
        self.assertIn("structuredContent", recall_payload["result"])
        structured = recall_payload["result"]["structuredContent"]
        self.assertIn("brief", structured)
        self.assertIn("trace", structured)
        brief_items = [
            item
            for slot_items in structured["brief"].values()
            for item in slot_items
        ]
        self.assertTrue(brief_items)
        self.assertTrue(any("runtime" in item.lower() for item in brief_items))
        self.assertTrue(structured["trace"]["selection_explanations"])

    def test_resources_and_prompts_expose_namespace_state(self) -> None:
        self._post_mcp(_initialize_payload())
        self._post_mcp(
            _jsonrpc(
                "tools/call",
                {
                    "name": "memory.recall",
                    "arguments": {
                        "namespace_id": self.namespace_id,
                        "agent_id": self.agent_id,
                        "query": "What should the planner remember?",
                        "context_budget_tokens": 750,
                    },
                },
                req_id=2,
            )
        )

        templates_response = self._post_mcp(_jsonrpc("resources/templates/list", req_id=3))
        template_names = {
            template["name"] for template in templates_response.json()["result"]["resourceTemplates"]
        }
        self.assertIn("namespace-summary", template_names)
        self.assertIn("latest-agent-brief", template_names)

        summary_response = self._post_mcp(
            _jsonrpc(
                "resources/read",
                {"uri": f"memory://namespaces/{self.namespace_id}/summary"},
                req_id=4,
            )
        )
        summary_payload = summary_response.json()["result"]["contents"][0]
        summary_data = summary_payload["text"]
        self.assertIn(self.namespace_id, summary_data)
        self.assertIn("active_memory_unit_count", summary_data)

        brief_response = self._post_mcp(
            _jsonrpc(
                "resources/read",
                {"uri": f"memory://namespaces/{self.namespace_id}/agents/{self.agent_id}/brief"},
                req_id=5,
            )
        )
        brief_data = brief_response.json()["result"]["contents"][0]["text"]
        self.assertIn("What should the planner remember?", brief_data)
        self.assertIn("selection_explanations", brief_data)

        prompts_response = self._post_mcp(_jsonrpc("prompts/list", req_id=6))
        prompt_names = {prompt["name"] for prompt in prompts_response.json()["result"]["prompts"]}
        self.assertIn("debug-memory-miss", prompt_names)
        self.assertIn("inspect-namespace-health", prompt_names)

        prompt_response = self._post_mcp(
            _jsonrpc(
                "prompts/get",
                {
                    "name": "prepare-memory-aware-task",
                    "arguments": {
                        "namespace_id": self.namespace_id,
                        "agent_id": self.agent_id,
                        "task": "prepare the next OpenClaw integration milestone",
                    },
                },
                req_id=7,
            )
        )
        prompt_payload = prompt_response.json()["result"]
        self.assertIn("messages", prompt_payload)
        self.assertIn("memory.recall", prompt_payload["messages"][0]["content"]["text"])

    def test_search_get_memory_and_metrics_work_over_mcp(self) -> None:
        self._post_mcp(_initialize_payload())
        search_response = self._post_mcp(
            _jsonrpc(
                "tools/call",
                {
                    "name": "memory.search",
                    "arguments": {
                        "namespace_id": self.namespace_id,
                        "agent_id": self.agent_id,
                        "query": "What storage stack does the runtime use?",
                        "limit": 3,
                    },
                },
                req_id=2,
            )
        )
        search_payload = search_response.json()["result"]["structuredContent"]
        self.assertTrue(search_payload["results"])
        memory_unit_id = search_payload["results"][0]["id"]

        memory_response = self._post_mcp(
            _jsonrpc(
                "tools/call",
                {
                    "name": "memory.get_memory_unit",
                    "arguments": {
                        "namespace_id": self.namespace_id,
                        "agent_id": self.agent_id,
                        "memory_unit_id": memory_unit_id,
                    },
                },
                req_id=3,
            )
        )
        memory_payload = memory_response.json()["result"]["structuredContent"]
        self.assertEqual(memory_payload["id"], memory_unit_id)
        self.assertIn("Postgres", memory_payload["content"])

        observability_response = self._post_mcp(
            _jsonrpc(
                "tools/call",
                {"name": "memory.get_observability_snapshot", "arguments": {}},
                req_id=4,
            )
        )
        self.assertIn("metrics", observability_response.json()["result"]["structuredContent"])

        metrics_response = self.client.get("/metrics")
        self.assertEqual(metrics_response.status_code, 200)
        self.assertIn("memory_runtime_mcp_requests_total", metrics_response.text)
        self.assertIn("memory_runtime_mcp_tool_calls_total", metrics_response.text)
        self.assertIn("memory_runtime_mcp_resource_reads_total", metrics_response.text)
        self.assertIn("memory_runtime_mcp_prompt_requests_total", metrics_response.text)

    def test_transport_validation_and_unknown_tool_errors(self) -> None:
        missing_accept = self.client.post(
            "/mcp/openclaw/http/alice",
            json=_initialize_payload(),
        )
        self.assertEqual(missing_accept.status_code, 406)

        wrong_content_type = self.client.post(
            "/mcp/openclaw/http/alice",
            content=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
            headers={"Accept": "application/json", "Content-Type": "text/plain"},
        )
        self.assertEqual(wrong_content_type.status_code, 415)

        invalid_json = self.client.post(
            "/mcp/openclaw/http/alice",
            content=b"not json",
            headers=MCP_HEADERS,
        )
        self.assertEqual(invalid_json.status_code, 400)

        unknown_tool = self._post_mcp(
            _jsonrpc("tools/call", {"name": "memory.nope", "arguments": {}}, req_id=9)
        )
        unknown_payload = unknown_tool.json()
        self.assertTrue(unknown_payload["result"]["isError"])
        self.assertIn("Unknown MCP tool", unknown_payload["result"]["content"][0]["text"])

    def test_delete_returns_method_not_allowed(self) -> None:
        response = self.client.delete(
            "/mcp/openclaw/http/alice",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 405)

    def test_search_results_reference_actual_memory_units(self) -> None:
        with get_engine().begin() as connection:
            memory_ids = list(connection.execute(select(MemoryUnit.id)).scalars().all())
        self.assertTrue(memory_ids)

        response = self._post_mcp(
            _jsonrpc(
                "tools/call",
                {
                    "name": "memory.search",
                    "arguments": {
                        "namespace_id": self.namespace_id,
                        "query": "architecture decisions",
                        "limit": 10,
                    },
                },
                req_id=11,
            )
        )
        result_ids = {
            item["id"] for item in response.json()["result"]["structuredContent"]["results"]
        }
        self.assertTrue(result_ids.intersection(memory_ids))
