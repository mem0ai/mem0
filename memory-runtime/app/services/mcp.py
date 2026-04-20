from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.memory_unit import MemoryUnit
from app.models.memory_space import MemorySpace
from app.repositories.agents import AgentRepository
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.memory_spaces import MemorySpaceRepository
from app.repositories.memory_units import MemoryUnitRepository
from app.repositories.namespaces import NamespaceRepository
from app.schemas.recall import RecallRequest
from app.services.observability import ObservabilityService
from app.services.retrieval import RetrievalService
from app.telemetry.metrics import increment_metric

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-03-26"


class MCPError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class MCPResourceTemplate:
    uri_template: str
    name: str
    description: str


@dataclass(frozen=True)
class MCPPrompt:
    name: str
    description: str
    arguments: list[dict[str, Any]]


class MCPService:
    def __init__(self, session: Session):
        self.session = session
        self.namespaces = NamespaceRepository(session)
        self.agents = AgentRepository(session)
        self.spaces = MemorySpaceRepository(session)
        self.memory_units = MemoryUnitRepository(session)
        self.audit = AuditLogRepository(session)
        self.retrieval = RetrievalService(session)
        self.observability = ObservabilityService(session)

    def handle_request(self, *, payload: dict[str, Any], client_name: str, user_id: str) -> dict[str, Any]:
        increment_metric("mcp_requests_total")
        request_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}

        if payload.get("jsonrpc") != JSONRPC_VERSION:
            return self._error(request_id, -32600, "Invalid JSON-RPC version.")
        if not isinstance(method, str):
            return self._error(request_id, -32600, "Missing JSON-RPC method.")

        try:
            result = self._dispatch(method=method, params=params, client_name=client_name, user_id=user_id)
        except MCPError as exc:
            increment_metric("mcp_errors_total")
            return self._error(request_id, exc.code, exc.message)
        except LookupError as exc:
            increment_metric("mcp_errors_total")
            return self._error(request_id, -32004, str(exc))
        except ValueError as exc:
            increment_metric("mcp_errors_total")
            return self._error(request_id, -32602, str(exc))
        except Exception as exc:  # pragma: no cover - defensive path
            increment_metric("mcp_errors_total")
            return self._error(request_id, -32603, f"Internal MCP error: {exc}")

        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "result": result,
        }

    def _dispatch(self, *, method: str, params: dict[str, Any], client_name: str, user_id: str) -> dict[str, Any]:
        if method == "initialize":
            return self._initialize_result(client_name=client_name, user_id=user_id)
        if method == "tools/list":
            return {"tools": [self._tool_payload(tool) for tool in self._tools()]}
        if method == "tools/call":
            increment_metric("mcp_tool_calls_total")
            return self._call_tool(params)
        if method in {"resources/templates/list", "resources/list"}:
            return {"resourceTemplates": [self._resource_template_payload(item) for item in self._resource_templates()]}
        if method == "resources/read":
            increment_metric("mcp_resource_reads_total")
            return self._read_resource(params)
        if method == "prompts/list":
            return {"prompts": [self._prompt_payload(prompt) for prompt in self._prompts()]}
        if method == "prompts/get":
            increment_metric("mcp_prompt_requests_total")
            return self._get_prompt(params)
        raise MCPError(-32601, f"Method '{method}' is not supported by this MCP server.")

    def _initialize_result(self, *, client_name: str, user_id: str) -> dict[str, Any]:
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "serverInfo": {
                "name": "agent-memory-runtime-mcp",
                "version": "0.1.0",
                "client": client_name,
                "user": user_id,
            },
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
        }

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(tool_name, str):
            raise MCPError(-32602, "tools/call requires a tool name.")

        if tool_name == "memory.recall":
            payload = RecallRequest(**arguments)
            response = self.retrieval.recall(payload)
            data = response.model_dump()
        elif tool_name == "memory.search":
            data = self._search(arguments)
        elif tool_name == "memory.list_spaces":
            data = self._list_spaces(arguments)
        elif tool_name == "memory.get_observability_snapshot":
            data = self.observability.stats().model_dump()
        elif tool_name == "memory.get_memory_unit":
            data = self._get_memory_unit(arguments)
        else:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown MCP tool '{tool_name}'."}],
            }

        return {
            "content": [{"type": "text", "text": self._json_text(data)}],
            "structuredContent": data,
            "isError": False,
        }

    def _search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        namespace_id = self._require_str(arguments, "namespace_id")
        query = self._require_str(arguments, "query")
        limit = int(arguments.get("limit", 5))
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        agent_id = arguments.get("agent_id")
        space_types = arguments.get("space_types")
        rows = self.memory_units.list_active_with_space(
            namespace_id=namespace_id,
            agent_id=agent_id,
            space_types=space_types,
        )
        ranked = []
        for memory, space_type in rows:
            score = self._score_search_candidate(query, memory.summary, memory.content, space_type)
            if score <= 0:
                continue
            ranked.append((score, memory, space_type))

        ranked.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        results = [
            {
                "id": memory.id,
                "summary": memory.summary,
                "content": memory.content,
                "kind": memory.kind,
                "scope": memory.scope,
                "space_type": space_type,
                "score": round(score, 3),
                "status": memory.status,
                "updated_at": self._isoformat(memory.updated_at),
            }
            for score, memory, space_type in ranked[:limit]
        ]
        return {"results": results, "query": query, "count": len(results)}

    def _list_spaces(self, arguments: dict[str, Any]) -> dict[str, Any]:
        namespace_id = self._require_str(arguments, "namespace_id")
        agent_id = arguments.get("agent_id")
        spaces = self.spaces.list_visible(namespace_id=namespace_id, agent_id=agent_id)
        return {
            "namespace_id": namespace_id,
            "agent_id": agent_id,
            "spaces": [
                {
                    "id": space.id,
                    "space_type": space.space_type,
                    "name": space.name,
                    "agent_id": space.agent_id,
                    "parent_space_id": space.parent_space_id,
                    "updated_at": self._isoformat(space.updated_at),
                }
                for space in spaces
            ],
        }

    def _get_memory_unit(self, arguments: dict[str, Any]) -> dict[str, Any]:
        namespace_id = self._require_str(arguments, "namespace_id")
        memory_unit_id = self._require_str(arguments, "memory_unit_id")
        agent_id = arguments.get("agent_id")
        row = self.memory_units.get_with_space(memory_unit_id)
        if row is None:
            raise LookupError(f"Memory unit '{memory_unit_id}' not found")
        memory, space_type = row
        if memory.namespace_id != namespace_id:
            raise LookupError(f"Memory unit '{memory_unit_id}' not found in namespace '{namespace_id}'")
        if agent_id is not None and memory.agent_id not in {None, agent_id}:
            raise LookupError(f"Memory unit '{memory_unit_id}' is not visible to agent '{agent_id}'")
        return {
            "id": memory.id,
            "namespace_id": memory.namespace_id,
            "agent_id": memory.agent_id,
            "space_type": space_type,
            "kind": memory.kind,
            "scope": memory.scope,
            "summary": memory.summary,
            "content": memory.content,
            "status": memory.status,
            "importance_score": memory.importance_score,
            "confidence_score": memory.confidence_score,
            "freshness_score": memory.freshness_score,
            "durability_score": memory.durability_score,
            "created_at": self._isoformat(memory.created_at),
            "updated_at": self._isoformat(memory.updated_at),
            "supersedes_memory_id": memory.supersedes_memory_id,
        }

    def _read_resource(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = self._require_str(params, "uri")
        data = self._resource_payload(uri)
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": self._json_text(data),
                }
            ]
        }

    def _resource_payload(self, uri: str) -> dict[str, Any]:
        parsed = urlparse(uri)
        if parsed.scheme != "memory":
            raise MCPError(-32602, f"Unsupported resource URI '{uri}'")

        parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc == "namespaces" and len(parts) >= 2:
            namespace_id = parts[0]
            section = parts[1]
            if section == "summary":
                return self._namespace_summary(namespace_id)
            if section == "observability":
                return self._namespace_observability(namespace_id)
            if section == "agents" and len(parts) >= 4:
                agent_id = parts[2]
                subsection = parts[3]
                if subsection == "brief":
                    return self._latest_agent_brief(namespace_id=namespace_id, agent_id=agent_id)
                if subsection == "spaces":
                    return self._list_spaces({"namespace_id": namespace_id, "agent_id": agent_id})

        raise MCPError(-32602, f"Unknown memory resource URI '{uri}'")

    def _namespace_summary(self, namespace_id: str) -> dict[str, Any]:
        namespace = self.namespaces.get_by_id(namespace_id)
        if namespace is None:
            raise LookupError(f"Namespace '{namespace_id}' not found")

        agents = self.agents.list_by_namespace(namespace_id)
        spaces = self.spaces.list_visible(namespace_id=namespace_id, agent_id=None)
        active_memory_count = self.session.execute(
            select(func.count(MemoryUnit.id))
            .where(MemoryUnit.namespace_id == namespace_id)
            .where(MemoryUnit.status == "active")
        ).scalar_one()

        return {
            "namespace": {
                "id": namespace.id,
                "name": namespace.name,
                "mode": namespace.mode,
                "status": namespace.status,
                "source_systems": namespace.source_systems,
                "created_at": self._isoformat(namespace.created_at),
                "updated_at": self._isoformat(namespace.updated_at),
            },
            "agents": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "source_system": agent.source_system,
                    "external_ref": agent.external_ref,
                }
                for agent in agents
            ],
            "space_counts": self._space_counts(spaces),
            "active_memory_unit_count": active_memory_count,
        }

    def _namespace_observability(self, namespace_id: str) -> dict[str, Any]:
        namespace = self.namespaces.get_by_id(namespace_id)
        if namespace is None:
            raise LookupError(f"Namespace '{namespace_id}' not found")
        payload = self.observability.stats().model_dump()
        payload["namespace"] = {
            "id": namespace.id,
            "name": namespace.name,
            "mode": namespace.mode,
        }
        return payload

    def _latest_agent_brief(self, *, namespace_id: str, agent_id: str) -> dict[str, Any]:
        namespace = self.namespaces.get_by_id(namespace_id)
        if namespace is None:
            raise LookupError(f"Namespace '{namespace_id}' not found")
        agent = self.agents.get_by_id(agent_id)
        if agent is None or agent.namespace_id != namespace_id:
            raise LookupError(f"Agent '{agent_id}' not found in namespace '{namespace_id}'")
        latest = self.audit.latest_by_action(
            namespace_id=namespace_id,
            action="recall_executed",
            agent_id=agent_id,
        )
        if latest is None:
            return {
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "last_recall": None,
            }
        return {
            "namespace_id": namespace_id,
            "agent_id": agent_id,
            "last_recall": latest.details_json,
            "recorded_at": self._isoformat(latest.created_at),
        }

    def _get_prompt(self, params: dict[str, Any]) -> dict[str, Any]:
        name = self._require_str(params, "name")
        arguments = params.get("arguments") or {}
        if name == "debug-memory-miss":
            namespace_id = self._require_str(arguments, "namespace_id")
            agent_id = self._require_str(arguments, "agent_id")
            expected_memory = self._require_str(arguments, "expected_memory")
            query = arguments.get("query", "Why did the runtime miss the expected memory?")
            text = (
                f"Investigate a memory miss for namespace '{namespace_id}' and agent '{agent_id}'. "
                f"Expected memory: {expected_memory}. "
                f"Original query: {query}. "
                "Inspect the latest recall trace, selected memories, and relevant memory units. "
                "Explain whether the miss came from ingestion, consolidation, ranking, or brief packing."
            )
        elif name == "prepare-memory-aware-task":
            namespace_id = self._require_str(arguments, "namespace_id")
            task = self._require_str(arguments, "task")
            agent_id = arguments.get("agent_id")
            session_id = arguments.get("session_id")
            text = (
                f"Prepare to work on task '{task}' in namespace '{namespace_id}'. "
                f"Agent id: {agent_id or 'n/a'}. Session id: {session_id or 'n/a'}. "
                "First call memory.recall with a focused query, then summarize the resulting memory brief "
                "before continuing with the task."
            )
        elif name == "inspect-namespace-health":
            namespace_id = self._require_str(arguments, "namespace_id")
            text = (
                f"Inspect namespace '{namespace_id}' health. "
                "Read the namespace summary and observability resources, then report on backlog, stalled jobs, "
                "recent recall activity, and any signs of memory quality degradation."
            )
        else:
            raise MCPError(-32602, f"Unknown prompt '{name}'")

        return {
            "description": next(prompt.description for prompt in self._prompts() if prompt.name == name),
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": text,
                    },
                }
            ],
        }

    @staticmethod
    def _tool_payload(tool: MCPTool) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }

    @staticmethod
    def _resource_template_payload(template: MCPResourceTemplate) -> dict[str, Any]:
        return {
            "uriTemplate": template.uri_template,
            "name": template.name,
            "description": template.description,
            "mimeType": "application/json",
        }

    @staticmethod
    def _prompt_payload(prompt: MCPPrompt) -> dict[str, Any]:
        return {
            "name": prompt.name,
            "description": prompt.description,
            "arguments": prompt.arguments,
        }

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    @staticmethod
    def _require_str(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"'{key}' is required")
        return value

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @classmethod
    def _json_text(cls, payload: dict[str, Any]) -> str:
        return json.dumps(payload, default=cls._json_default, indent=2, sort_keys=True)

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _space_counts(spaces: list[MemorySpace]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for space in spaces:
            counts[space.space_type] = counts.get(space.space_type, 0) + 1
        return counts

    @staticmethod
    def _score_search_candidate(query: str, summary: str, content: str, space_type: str) -> float:
        query_tokens = RetrievalService._normalize_tokens(query)
        summary_tokens = RetrievalService._normalize_tokens(summary)
        content_tokens = RetrievalService._normalize_tokens(content)
        overlap = len(query_tokens & summary_tokens) * 2 + len(query_tokens & content_tokens)
        if space_type == "project-space":
            overlap += 0.3
        if space_type == "agent-core":
            overlap += 0.15
        return float(overlap)

    @staticmethod
    def _tools() -> list[MCPTool]:
        return [
            MCPTool(
                name="memory.recall",
                description="Build a structured memory brief for an agent or namespace query.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "namespace_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                        "session_id": {"type": "string"},
                        "query": {"type": "string"},
                        "context_budget_tokens": {"type": "integer", "minimum": 1},
                        "space_filter": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["namespace_id", "query", "context_budget_tokens"],
                },
            ),
            MCPTool(
                name="memory.search",
                description="Search active long-term memories visible to an agent in a namespace.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "namespace_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1},
                        "space_types": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["namespace_id", "query"],
                },
            ),
            MCPTool(
                name="memory.list_spaces",
                description="List visible memory spaces for an agent or an entire namespace.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "namespace_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                    },
                    "required": ["namespace_id"],
                },
            ),
            MCPTool(
                name="memory.get_observability_snapshot",
                description="Fetch the current runtime observability snapshot and job breakdown.",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            MCPTool(
                name="memory.get_memory_unit",
                description="Fetch a single memory unit that is visible inside a namespace scope.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "namespace_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                        "memory_unit_id": {"type": "string"},
                    },
                    "required": ["namespace_id", "memory_unit_id"],
                },
            ),
        ]

    @staticmethod
    def _resource_templates() -> list[MCPResourceTemplate]:
        return [
            MCPResourceTemplate(
                uri_template="memory://namespaces/{namespace_id}/summary",
                name="namespace-summary",
                description="Summary of a namespace, its agents, spaces, and active memory counts.",
            ),
            MCPResourceTemplate(
                uri_template="memory://namespaces/{namespace_id}/agents/{agent_id}/brief",
                name="latest-agent-brief",
                description="Most recent recall brief recorded for an agent.",
            ),
            MCPResourceTemplate(
                uri_template="memory://namespaces/{namespace_id}/observability",
                name="namespace-observability",
                description="Current observability snapshot for the runtime with namespace metadata.",
            ),
            MCPResourceTemplate(
                uri_template="memory://namespaces/{namespace_id}/agents/{agent_id}/spaces",
                name="agent-spaces",
                description="Visible memory spaces for an agent in a namespace.",
            ),
        ]

    @staticmethod
    def _prompts() -> list[MCPPrompt]:
        return [
            MCPPrompt(
                name="debug-memory-miss",
                description="Guide an operator or agent through debugging a missing memory recall.",
                arguments=[
                    {"name": "namespace_id", "required": True},
                    {"name": "agent_id", "required": True},
                    {"name": "expected_memory", "required": True},
                    {"name": "query", "required": False},
                ],
            ),
            MCPPrompt(
                name="prepare-memory-aware-task",
                description="Prepare a task flow that explicitly consults memory before execution.",
                arguments=[
                    {"name": "namespace_id", "required": True},
                    {"name": "agent_id", "required": False},
                    {"name": "session_id", "required": False},
                    {"name": "task", "required": True},
                ],
            ),
            MCPPrompt(
                name="inspect-namespace-health",
                description="Inspect runtime health, backlog, and memory quality signals for a namespace.",
                arguments=[
                    {"name": "namespace_id", "required": True},
                ],
            ),
        ]
