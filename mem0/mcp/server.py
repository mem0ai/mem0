"""
Mem0 MCP Server — Agent Memory Protocol / Model Context Protocol server integrated natively in Mem0.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from mcp.server.fastmcp import FastMCP
import mcp.types as types
from mcp.shared.exceptions import McpError

from mem0 import MemoryClient, Memory
from mem0.llms.base import LLMBase
from mem0.utils.factory import LlmFactory, EmbedderFactory
from mem0.embeddings.mock import MockEmbeddings
from mem0.memory.main import lemmatize_for_bm25

# ── §3.5 Error mapping ────────────────────────────────────────────────────────
_AMP_TO_JSONRPC = {
    "invalid_request": -32602,
    "not_found": -32001,
    "not_supported": -32002,
    "backend_error": -32000,
}


class AmpToolError(Exception):
    def __init__(self, amp_error_code: str, message: str):
        if amp_error_code not in _AMP_TO_JSONRPC:
            raise ValueError(f"unknown amp_error_code: {amp_error_code}")
        self.amp_error_code = amp_error_code
        self.message = message
        super().__init__(f"[{amp_error_code}] {message}")


# Monkeypatch types.Implementation to automatically inject amp_conformance and amp_version fields.
original_impl_init = types.Implementation.__init__

def custom_impl_init(self, *args, **kwargs):
    kwargs.setdefault("amp_conformance", "core")
    kwargs.setdefault("amp_version", "1.1")
    original_impl_init(self, *args, **kwargs)

types.Implementation.__init__ = custom_impl_init


mcp = FastMCP(
    "mem0-mcp",
    instructions=(
        "AMP (Agent Memory Protocol) Core-conformant memory server wrapping Mem0. "
        "Implements amp.encode, amp.recall, amp.forget, amp.stats, amp.update, amp.batch_encode."
    ),
)


# Monkeypatch CallToolRequest handler to translate tool exceptions/error results
# into JSON-RPC error frames using the §3.5 mapping table.
original_call_tool_handler = mcp._mcp_server.request_handlers[types.CallToolRequest]


def _extract_amp_error_from_text(text: str) -> Optional[Tuple[str, str]]:
    if not text:
        return None

    marker = "Error executing tool"
    if text.startswith(marker):
        colon = text.find(":")
        if colon != -1:
            text = text[colon + 1 :].lstrip()

    if text.startswith("["):
        end = text.find("]")
        if end >= 2:
            code = text[1:end]
            if code in _AMP_TO_JSONRPC:
                message = text[end + 1 :].lstrip()
                return code, message

    if "validation error" in text.lower() or "field required" in text.lower():
        return "invalid_request", text

    return None


async def custom_call_tool_handler(req: types.CallToolRequest) -> types.ServerResult:
    res = await original_call_tool_handler(req)
    if hasattr(res, "root") and isinstance(res.root, types.CallToolResult) and res.root.isError:
        raw = res.root.content[0].text if res.root.content else "Unknown tool error"
        parsed = _extract_amp_error_from_text(raw)
        if parsed is not None:
            amp_code, message = parsed
        else:
            amp_code, message = "backend_error", raw
        jsonrpc_code = _AMP_TO_JSONRPC[amp_code]
        raise McpError(
            types.ErrorData(
                code=jsonrpc_code,
                message=message,
                data={"amp_error_code": amp_code, "message": message},
            )
        )
    return res


mcp._mcp_server.request_handlers[types.CallToolRequest] = custom_call_tool_handler

# ── Scope handling ────────────────────────────────────────────────────────────
ISOLATING_KEYS = ("agent_id", "group_id", "workspace_id", "user_id")
NON_ISOLATING_KEYS = ("session_id", "app_id", "org_id")
ALL_SCOPE_KEYS = ISOLATING_KEYS + NON_ISOLATING_KEYS


def _normalize_scope(
    scope: Optional[Dict[str, Any]],
    agent_id: Optional[str],
) -> Dict[str, str]:
    if scope is not None:
        if not isinstance(scope, dict):
            raise AmpToolError("invalid_request", "scope must be an object")
        unknown = set(scope.keys()) - set(ALL_SCOPE_KEYS)
        if unknown:
            raise AmpToolError(
                "invalid_request",
                f"scope contains unknown keys: {sorted(unknown)}",
            )
        for k, v in scope.items():
            if isinstance(v, (dict, list)):
                raise AmpToolError(
                    "invalid_request",
                    f"scope key '{k}' contains nested structure which is not allowed",
                )
        normalized = {k: v for k, v in scope.items() if v is not None and v != ""}
        if agent_id:
            existing = normalized.get("agent_id")
            if existing and existing != agent_id:
                raise AmpToolError(
                    "invalid_request",
                    "agent_id provided both as scope.agent_id and top-level disagree",
                )
            normalized.setdefault("agent_id", agent_id)
    elif agent_id:
        normalized = {"agent_id": agent_id}
    else:
        raise AmpToolError(
            "invalid_request",
            "either scope or agent_id is required",
        )

    if not any(normalized.get(k) for k in ISOLATING_KEYS):
        raise AmpToolError(
            "invalid_request",
            "scope must include at least one isolating identity key "
            f"({', '.join(ISOLATING_KEYS)})",
        )

    return {k: str(v) for k, v in normalized.items()}


def _scope_namespace_key(scope: Dict[str, str]) -> str:
    if list(scope.keys()) == ["agent_id"]:
        return scope["agent_id"]
    canonical = json.dumps(scope, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"scope-{digest}"


def merge_patch(target: Any, patch: Any) -> Any:
    if isinstance(patch, dict):
        if not isinstance(target, dict):
            target = {}
        result = dict(target)
        for k, v in patch.items():
            if v is None:
                result.pop(k, None)
            else:
                result[k] = merge_patch(result.get(k), v)
        return result
    else:
        return patch


# ── Mem0 Client Initialization ────────────────────────────────────────────────
_mem0_client = None
_storage_path = os.environ.get("AMP_STORAGE_PATH", os.path.expanduser("~/.amp/mem0"))


def _get_mem0():
    global _mem0_client
    if _mem0_client is not None:
        return _mem0_client

    api_key = os.environ.get("MEM0_API_KEY")
    if api_key:
        _mem0_client = MemoryClient(api_key=api_key)
    else:
        # Mock LLM and Embedder to avoid external OpenAI calls in local mode

        class MockLLM(LLMBase):
            def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
                user_msg = ""
                for m in messages:
                    if m.get("role") == "user":
                        user_msg = m.get("content") or ""
                
                # Extract text after user:
                lines = user_msg.split("\n")
                user_lines = []
                for line in lines:
                    if line.lstrip().startswith("user:"):
                        user_lines.append(line.lstrip()[5:].strip())
                if user_lines:
                    text = " ".join(user_lines)
                else:
                    text = user_msg.strip()
                
                return json.dumps({"memory": [{"text": text, "event": "ADD"}]})

        original_llm_create = LlmFactory.create
        def custom_llm_create(provider_name: str, config=None, **kwargs):
            if provider_name == "openai":
                return MockLLM(config)
            return original_llm_create(provider_name, config, **kwargs)
        LlmFactory.create = custom_llm_create

        original_embedder_create = EmbedderFactory.create
        def custom_embedder_create(provider_name, config, vector_config=None):
            if provider_name == "openai":
                return MockEmbeddings()
            return original_embedder_create(provider_name, config, vector_config)
        EmbedderFactory.create = custom_embedder_create

        os.makedirs(_storage_path, exist_ok=True)
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "mock-model"
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "mock-model",
                    "embedding_model_dims": 10
                }
            },
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "path": os.path.join(_storage_path, "chroma")
                }
            },
            "history_db_path": os.path.join(_storage_path, "history.db")
        }
        _mem0_client = Memory.from_config(config)

        # Monkeypatch Memory._update_memory to support metadata deletion and replace mode.
        def custom_update_memory(self, memory_id, data, existing_embeddings, metadata=None):
            logger = logging.getLogger("mem0")
            logger.info(f"Updating memory with {data=}")

            try:
                existing_memory = self.vector_store.get(vector_id=memory_id)
            except Exception:
                logger.error(f"Error getting memory with ID {memory_id} during update.")
                raise ValueError(f"Error getting memory with ID {memory_id}. Please provide a valid 'memory_id'")

            if existing_memory is None:
                raise ValueError(f"Memory with id {memory_id} not found. Please provide a valid 'memory_id'")

            prev_value = existing_memory.payload.get("data")

            # Define system/protected keys that Mem0 manages
            SYSTEM_KEYS = {
                "user_id", "agent_id", "run_id", "hash", "data",
                "created_at", "updated_at", "text_lemmatized", "actor_id", "role",
                "_amp_scope", "amp.source", "amp.status", "amp.metadata_json"
            }

            new_metadata = {}
            for k, v in existing_memory.payload.items():
                if k in SYSTEM_KEYS:
                    new_metadata[k] = deepcopy(v)

            if metadata is not None:
                new_metadata.update(metadata)

            new_metadata["data"] = data
            new_metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
            new_metadata["text_lemmatized"] = lemmatize_for_bm25(data)
            new_metadata["created_at"] = existing_memory.payload.get("created_at")
            new_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

            # actor_id is immutable after creation
            if "actor_id" in existing_memory.payload:
                new_metadata["actor_id"] = existing_memory.payload["actor_id"]

            if data in existing_embeddings:
                embeddings = existing_embeddings[data]
            else:
                embeddings = self.embedding_model.embed(data, "update")

            self.vector_store.update(
                vector_id=memory_id,
                vector=embeddings,
                payload=new_metadata,
            )
            logger.info(f"Updating memory with ID {memory_id=} with {data=}")

            self.db.add_history(
                memory_id,
                prev_value,
                data,
                "UPDATE",
                created_at=new_metadata["created_at"],
                updated_at=new_metadata["updated_at"],
                actor_id=new_metadata.get("actor_id"),
                role=new_metadata.get("role"),
            )

            session_filters = {k: new_metadata[k] for k in ("user_id", "agent_id", "run_id") if new_metadata.get(k)}
            self._remove_memory_from_entity_store(memory_id, session_filters)
            self._link_entities_for_memory(memory_id, data, session_filters)

            return memory_id

        Memory._update_memory = custom_update_memory
    return _mem0_client


def _is_platform_mode() -> bool:
    return os.environ.get("MEM0_API_KEY") is not None


# ── Recall Post-Filtering Helper ──────────────────────────────────────────────
def _parse_iso8601(value: Any, *, field: str) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AmpToolError("invalid_request", f"{field} must be an ISO 8601 string")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AmpToolError(
            "invalid_request", f"{field} is not a valid ISO 8601 timestamp: {exc}"
        ) from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _eval_metadata_filter(stored: Any, op: str, value: Any) -> bool:
    if op == "eq":
        if isinstance(stored, bool) != isinstance(value, bool):
            return False
        return stored == value
    if op == "ne":
        if isinstance(stored, bool) != isinstance(value, bool):
            return False
        stored_is_num = isinstance(stored, (int, float)) and not isinstance(stored, bool)
        value_is_num = isinstance(value, (int, float)) and not isinstance(value, bool)
        stored_is_str = isinstance(stored, str)
        value_is_str = isinstance(value, str)
        if (stored_is_num != value_is_num) or (stored_is_str != value_is_str):
            return False
        return stored != value
    if op in ("gt", "gte", "lt", "lte"):
        if isinstance(stored, bool) or isinstance(value, bool):
            return False
        stored_kind = "num" if isinstance(stored, (int, float)) else ("str" if isinstance(stored, str) else None)
        value_kind = "num" if isinstance(value, (int, float)) else ("str" if isinstance(value, str) else None)
        if stored_kind is None or stored_kind != value_kind:
            return False
        try:
            if op == "gt":
                return stored > value
            if op == "gte":
                return stored >= value
            if op == "lt":
                return stored < value
            if op == "lte":
                return stored <= value
        except Exception:
            return False
    if op == "in":
        return stored in value
    if op == "contains":
        if isinstance(stored, list):
            return value in stored
        if isinstance(stored, str):
            return value in stored
    return False


def _apply_post_filters(
    results: list[dict],
    filters: Optional[dict],
) -> list[dict]:
    if not filters:
        return results

    filtered = []
    ts_after = _parse_iso8601(filters.get("timestamp_after"), field="filters.timestamp_after")
    ts_before = _parse_iso8601(filters.get("timestamp_before"), field="filters.timestamp_before")
    status_filter = filters.get("status")
    source_filter = filters.get("source")
    metadata_filters = filters.get("metadata_filters")

    if metadata_filters is not None:
        _validate_metadata_filters(metadata_filters)

    for item in results:
        # 1. Status Filter
        if status_filter:
            if item.get("status") != status_filter:
                continue
        else:
            if item.get("status") == "archived":
                continue

        # 2. Source Filter
        if source_filter and item.get("source") != source_filter:
            continue

        # 3. Timestamp Filter
        raw_ts = item.get("timestamp")
        if raw_ts:
            candidate = raw_ts[:-1] + "+00:00" if raw_ts.endswith("Z") else raw_ts
            try:
                row_ts = datetime.fromisoformat(candidate)
                if row_ts.tzinfo is None:
                    row_ts = row_ts.replace(tzinfo=timezone.utc)
                if ts_after is not None and not (row_ts > ts_after):
                    continue
                if ts_before is not None and not (row_ts < ts_before):
                    continue
            except ValueError:
                continue

        # 4. Metadata filters (strict-AND)
        if metadata_filters:
            item_metadata = item.get("metadata") or {}
            match = True
            for pred in metadata_filters:
                key = pred["key"]
                op = pred["operator"]
                val = pred["value"]
                if key not in item_metadata:
                    match = False
                    break
                if not _eval_metadata_filter(item_metadata[key], op, val):
                    match = False
                    break
            if not match:
                continue

        filtered.append(item)

    return filtered


def _validate_metadata_filters(filters: Any) -> None:
    if not isinstance(filters, list):
        raise AmpToolError(
            "invalid_request",
            "filters.metadata_filters must be an array of MetadataFilter objects",
        )
    if len(filters) > 32:
        raise AmpToolError(
            "invalid_request",
            "filters.metadata_filters length exceeds maxItems=32",
        )
    for idx, entry in enumerate(filters):
        if not isinstance(entry, dict):
            raise AmpToolError(
                "invalid_request",
                f"filters.metadata_filters[{idx}] must be an object",
            )
        for required in ("key", "operator", "value"):
            if required not in entry:
                raise AmpToolError(
                    "invalid_request",
                    f"filters.metadata_filters[{idx}].{required} is required",
                )
        key = entry["key"]
        op = entry["operator"]
        value = entry["value"]
        if not isinstance(key, str) or not key:
            raise AmpToolError(
                "invalid_request",
                f"filters.metadata_filters[{idx}].key must be a non-empty string",
            )
        if op not in ("eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"):
            raise AmpToolError(
                "invalid_request",
                f"filters.metadata_filters[{idx}].operator '{op}' is not valid",
            )
        if op == "in":
            if not isinstance(value, list):
                raise AmpToolError(
                    "invalid_request",
                    f"filters.metadata_filters[{idx}].value must be an array when operator='in'",
                )
            for elem_idx, elem in enumerate(value):
                if not (isinstance(elem, (str, int, float)) and not isinstance(elem, bool)):
                    if not isinstance(elem, bool):
                        raise AmpToolError(
                            "invalid_request",
                            f"filters.metadata_filters[{idx}].value[{elem_idx}] must be scalar",
                        )
        else:
            if not (isinstance(value, (str, int, float)) or isinstance(value, bool)):
                raise AmpToolError(
                    "invalid_request",
                    f"filters.metadata_filters[{idx}].value must be scalar",
                )


def _validate_metadata_bag(metadata: Any, *, field: str) -> None:
    if metadata is None:
        return
    if not isinstance(metadata, dict):
        raise AmpToolError("invalid_request", f"{field} must be an object")
    try:
        encoded = json.dumps(metadata, ensure_ascii=False)
    except Exception as exc:
        raise AmpToolError(
            "invalid_request", f"{field} is not JSON-serialisable: {exc}"
        )
    if len(encoded.encode("utf-8")) > 64 * 1024:
        raise AmpToolError(
            "invalid_request",
            f"{field} exceeds 64 KiB cap",
        )


# ── amp.encode ────────────────────────────────────────────────────────────────
@mcp.tool(
    name="amp.encode",
    description="Store a new memory for an agent in Mem0.",
    annotations=types.ToolAnnotations(
        title="Encode Memory",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def amp_encode(
    content: str,
    agent_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
    source: str = "direct",
    force: bool = False,
    private: Optional[bool] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise AmpToolError("invalid_request", "content must be a non-empty string")

    if source not in ("direct", "user_stated", "inferred", "external"):
        raise AmpToolError(
            "invalid_request",
            f"source '{source}' is not a valid MemorySource enum value",
        )

    if metadata is not None:
        _validate_metadata_bag(metadata, field="metadata")

    norm_scope = _normalize_scope(scope, agent_id)
    scope_key = _scope_namespace_key(norm_scope)

    # Initialize / fetch client
    client = _get_mem0()

    meta = {}
    meta["amp.source"] = source
    meta["amp.status"] = "active"
    # Save original scope for round-trip MXF
    meta["_amp_scope"] = json.dumps(norm_scope)
    if metadata is not None:
        meta["amp.metadata_json"] = json.dumps(metadata)

    # Save to Mem0
    try:
        if _is_platform_mode():
            # Platform client
            res = client.add(content, user_id=scope_key, metadata=meta, infer=not force)
        else:
            # Local client
            res = client.add(content, user_id=scope_key, metadata=meta, infer=not force)
    except Exception as exc:
        raise AmpToolError("backend_error", f"Mem0 add failed: {exc}")

    # Parse return value
    mem_id = None
    if isinstance(res, list) and res:
        mem_id = res[0].get("id")
    elif isinstance(res, dict):
        results_list = res.get("results")
        if isinstance(results_list, list) and results_list:
            mem_id = results_list[0].get("id")
        else:
            mem_id = res.get("id") or res.get("event_id")

    if not mem_id:
        return {"status": "below_threshold"}

    response = {"id": mem_id, "status": "stored"}
    if private is not None:
        response["visibility"] = "private" if private else "shared"
    return response


# ── amp.recall ────────────────────────────────────────────────────────────────
@mcp.tool(
    name="amp.recall",
    description="Retrieve memories relevant to a query from Mem0.",
    annotations=types.ToolAnnotations(
        title="Recall Memories",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def amp_recall(
    query: str,
    agent_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    norm_scope = _normalize_scope(scope, agent_id)
    scope_key = _scope_namespace_key(norm_scope)

    client = _get_mem0()

    # Oversampling for post-filtering
    limit = min(top_k * 10, 200)

    try:
        if _is_platform_mode():
            res = client.search(query, user_id=scope_key, limit=limit)
        else:
            res = client.search(query, filters={"user_id": scope_key}, limit=limit)
    except Exception as exc:
        raise AmpToolError("backend_error", f"Mem0 search failed: {exc}")

    # Mem0 search returns a list of items directly or in {"results": [...]}
    raw_results = []
    if isinstance(res, list):
        raw_results = res
    elif isinstance(res, dict):
        raw_results = res.get("results") or []

    # Map to AMP results
    amp_results = []
    for item in raw_results:
        content = item.get("memory") or item.get("content") or ""
        m_id = item.get("id") or ""
        score = item.get("score") or item.get("similarity") or 0.0
        meta = item.get("metadata") or {}
        status = meta.get("amp.status") or "active"
        source = meta.get("amp.source") or "direct"
        ts = item.get("created_at") or item.get("updated_at") or datetime.now(timezone.utc).isoformat()

        # Clean metadata for return
        orig_scope_str = meta.get("_amp_scope")
        
        orig_scope = norm_scope
        if orig_scope_str:
            try:
                orig_scope = json.loads(orig_scope_str)
            except Exception:
                pass

        user_metadata = {}
        if "amp.metadata_json" in meta:
            try:
                user_metadata = json.loads(meta["amp.metadata_json"])
            except Exception:
                pass
        else:
            user_metadata = {k: v for k, v in meta.items() if k not in {
                "user_id", "agent_id", "run_id", "hash", "data", "created_at", "updated_at",
                "text_lemmatized", "actor_id", "role", "_amp_scope", "amp.source", "amp.status"
            }}

        amp_results.append({
            "id": m_id,
            "content": content,
            "score": score,
            "source": source,
            "timestamp": ts,
            "status": status,
            "scope": orig_scope,
            "metadata": user_metadata,
        })

    # Apply filters
    filtered_results = _apply_post_filters(amp_results, filters)

    # Sort descending by score
    filtered_results.sort(key=lambda m: m["score"], reverse=True)

    return {"results": filtered_results[:top_k]}


# ── amp.forget ────────────────────────────────────────────────────────────────
@mcp.tool(
    name="amp.forget",
    description="Permanently delete a memory from Mem0.",
    annotations=types.ToolAnnotations(
        title="Forget Memory",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def amp_forget(
    id: str,
    agent_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    norm_scope = _normalize_scope(scope, agent_id)
    scope_key = _scope_namespace_key(norm_scope)

    client = _get_mem0()

    # Enforce existence and scope-isolation check before deleting
    try:
        item = client.get(id)
        if not item:
            return {"status": "not_found"}
        stored_user_id = item.get("user_id") or item.get("metadata", {}).get("user_id")
        if stored_user_id != scope_key:
            return {"status": "not_found"}
    except Exception:
        return {"status": "not_found"}

    try:
        client.delete(id)
        return {"status": "forgotten"}
    except Exception as exc:
        raise AmpToolError("backend_error", f"Mem0 delete failed: {exc}")


# ── amp.stats ─────────────────────────────────────────────────────────────────
@mcp.tool(
    name="amp.stats",
    description="Return Mem0 statistics for the given scope.",
    annotations=types.ToolAnnotations(
        title="Stats",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def amp_stats(
    agent_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    norm_scope = _normalize_scope(scope, agent_id)
    scope_key = _scope_namespace_key(norm_scope)

    client = _get_mem0()

    try:
        if _is_platform_mode():
            res = client.get_all(user_id=scope_key)
        else:
            res = client.get_all(filters={"user_id": scope_key})
    except Exception as exc:
        raise AmpToolError("backend_error", f"Mem0 get_all failed: {exc}")

    count = 0
    if isinstance(res, dict):
        count = res.get("count") or len(res.get("results", []))
    elif isinstance(res, list):
        count = len(res)

    return {
        "memory_count": count,
        "unconsolidated_count": 0,
        "metadata": {}
    }


# ── amp.update ────────────────────────────────────────────────────────────────
@mcp.tool(
    name="amp.update",
    description="Mutate the content and/or metadata of an existing memory in place in Mem0.",
    annotations=types.ToolAnnotations(
        title="Update Memory",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def amp_update(
    id: str,
    agent_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
    content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    metadata_mode: str = "merge",
) -> Dict[str, Any]:
    if content is not None and (not isinstance(content, str) or not content.strip()):
        raise AmpToolError("invalid_request", "content must be a non-empty string")

    norm_scope = _normalize_scope(scope, agent_id)
    scope_key = _scope_namespace_key(norm_scope)

    client = _get_mem0()

    # Verify existence and scope isolation
    try:
        item = client.get(id)
        if not item:
            return {"status": "not_found"}
        stored_user_id = item.get("user_id") or item.get("metadata", {}).get("user_id")
        if stored_user_id != scope_key:
            return {"status": "not_found"}
    except Exception:
        return {"status": "not_found"}

    # Determine updated content and metadata
    existing_content = item.get("memory") or item.get("content") or ""
    raw_meta = item.get("metadata") or {}
    existing_metadata = {}
    if "amp.metadata_json" in raw_meta:
        try:
            existing_metadata = json.loads(raw_meta["amp.metadata_json"])
        except Exception:
            pass
    else:
        existing_metadata = {k: v for k, v in raw_meta.items() if k not in {
            "user_id", "agent_id", "run_id", "hash", "data", "created_at", "updated_at",
            "text_lemmatized", "actor_id", "role", "_amp_scope", "amp.source", "amp.status"
        }}

    new_content = content if content is not None else existing_content

    if metadata is not None:
        _validate_metadata_bag(metadata, field="metadata")
        if metadata_mode not in ("merge", "replace"):
            raise AmpToolError("invalid_request", f"metadata_mode must be 'merge' or 'replace', got {metadata_mode!r}")
            
        if metadata_mode == "merge":
            new_user_metadata = merge_patch(existing_metadata, metadata)
        else:  # replace
            new_user_metadata = dict(metadata)
    else:
        new_user_metadata = existing_metadata

    # Check for no-op
    if new_content == existing_content and new_user_metadata == existing_metadata:
        return {"status": "no_change", "id": id}

    # Construct the actual payload for Mem0
    meta_for_update = {}
    meta_for_update["amp.metadata_json"] = json.dumps(new_user_metadata)
    for k in ("amp.source", "amp.status", "_amp_scope"):
        if k in raw_meta:
            meta_for_update[k] = raw_meta[k]

    # Call Mem0 update
    try:
        try:
            client.update(id, data=new_content, metadata=meta_for_update)
        except TypeError:
            client.update(id, text=new_content, metadata=meta_for_update)
    except Exception as exc:
        raise AmpToolError("backend_error", f"Mem0 update failed: {exc}")

    return {"status": "updated", "id": id}


# ── amp.batch_encode ──────────────────────────────────────────────────────────
@mcp.tool(
    name="amp.batch_encode",
    description="Store multiple memories in a single round-trip in Mem0.",
    annotations=types.ToolAnnotations(
        title="Batch Encode Memories",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def amp_batch_encode(
    entries: list,
    agent_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(entries, list):
        raise AmpToolError("invalid_request", "entries must be an array")
    if len(entries) > 1000:
        raise AmpToolError("invalid_request", "batch size exceeds 1000")

    norm_scope = _normalize_scope(scope, agent_id)
    scope_key = _scope_namespace_key(norm_scope)

    client = _get_mem0()

    results = []
    counts = {"stored": 0, "below_threshold": 0, "duplicate": 0, "failed": 0}

    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            results.append({"status": "invalid_request", "message": "entry must be an object"})
            counts["failed"] += 1
            continue

        # Validate row-level keys
        allowed = {"content", "source", "force", "metadata"}
        extra = set(entry.keys()) - allowed
        if extra:
            results.append({
                "status": "invalid_request",
                "message": f"unsupported row keys: {sorted(extra)}"
            })
            counts["failed"] += 1
            continue

        content = entry.get("content")
        if not isinstance(content, str) or not content.strip():
            results.append({"status": "invalid_request", "message": "content must be non-empty"})
            counts["failed"] += 1
            continue

        source = entry.get("source", "direct")
        if not isinstance(source, str) or source not in ("direct", "user_stated", "inferred", "external"):
            results.append({
                "status": "invalid_request",
                "message": f"source '{source}' is not a valid MemorySource enum value"
            })
            counts["failed"] += 1
            continue

        force = entry.get("force", False)
        if not isinstance(force, bool):
            results.append({"status": "invalid_request", "message": "force must be a boolean"})
            counts["failed"] += 1
            continue

        meta = entry.get("metadata")
        if meta is not None:
            try:
                _validate_metadata_bag(meta, field="metadata")
            except AmpToolError as exc:
                results.append({"status": "invalid_request", "message": exc.message})
                counts["failed"] += 1
                continue

        # Add single entry
        row_meta = {}
        row_meta["amp.source"] = source
        row_meta["amp.status"] = "active"
        row_meta["_amp_scope"] = json.dumps(norm_scope)
        if meta is not None:
            row_meta["amp.metadata_json"] = json.dumps(meta)

        try:
            res = client.add(content, user_id=scope_key, metadata=row_meta, infer=not force)
            mem_id = None
            if isinstance(res, list) and res:
                mem_id = res[0].get("id")
            elif isinstance(res, dict):
                results_list = res.get("results")
                if isinstance(results_list, list) and results_list:
                    mem_id = results_list[0].get("id")
                else:
                    mem_id = res.get("id") or res.get("event_id")

            if mem_id:
                results.append({"id": mem_id, "status": "stored"})
                counts["stored"] += 1
            else:
                results.append({"status": "below_threshold"})
                counts["below_threshold"] += 1
        except Exception as exc:
            results.append({"status": "backend_error", "message": str(exc)})
            counts["failed"] += 1

    return {"results": results, "summary": counts}


# ── Full conformance dummy verbs ─────────────────────────────────────────────
@mcp.tool(
    name="amp.pin",
    description="Mark a memory as permanent (not_supported on Mem0 core wrapper).",
    annotations=types.ToolAnnotations(
        title="Pin Memory",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def amp_pin(
    id: str,
    agent_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {"status": "not_supported"}


@mcp.tool(
    name="amp.consolidate",
    description="Trigger consolidation (not_supported on Mem0 core wrapper).",
    annotations=types.ToolAnnotations(
        title="Consolidate Memories",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def amp_consolidate(
    agent_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
    depth: str = "full",
) -> Dict[str, Any]:
    return {"status": "not_supported"}


def main():
    parser = argparse.ArgumentParser(description="Mem0 MCP Server")
    parser.add_argument("--storage-path", help="Local storage directory path")
    args, unknown = parser.parse_known_args()

    if args.storage_path:
        global _storage_path
        _storage_path = os.path.abspath(args.storage_path)

    # Launch FastMCP server
    mcp.run()


if __name__ == "__main__":
    main()
