#!/usr/bin/env python3
"""Expose Mem0's memory search as one local Claude Code tool."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import telemetry
from memory_core import (
    CODING_MEMORY_CATEGORY_NAMES,
    format_search_result,
    resolve_repo,
    SEARCH_SCOPES,
    search_memories,
)


PROTOCOL_VERSION = "2024-11-05"
TOOL_NAME = "search_memories"
TOOL_DESCRIPTION = (
    "Search memories from earlier work in this repository. ALWAYS call this "
    "tool before answering anything that could depend on prior context: the "
    "user's preferences, facts about this codebase, history, people, projects, "
    "or earlier decisions. Do not rely on the chat window alone. The "
    "repository's memory is shared by everyone who works in it and includes "
    "what it took to run, test, or build here, so search before assuming an "
    "invocation works. The scope argument changes what is searched: 'repo' "
    "(default) is the whole repository's shared memory plus your own "
    "preferences, 'dir' narrows the shared part to the directory you are "
    "working in, and 'mine' is your preferences alone. Pass run_id to look "
    "at one earlier Claude Code session only."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "minLength": 1,
            "maxLength": 2000,
            "description": "A direct question about earlier work in this repository.",
        },
        "top_k": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
            "description": "Maximum memories to return. Uses Mem0's configured default when omitted.",
        },
        "category": {
            "type": "string",
            "enum": list(CODING_MEMORY_CATEGORY_NAMES),
            "description": "Optional memory category. Omit to search every category.",
        },
        "scope": {
            "type": "string",
            "enum": list(SEARCH_SCOPES),
            "description": (
                "Which memories to search. 'repo' (default) is the whole repository's "
                "shared memory plus your own preferences, 'dir' narrows the shared "
                "part to the current directory, 'mine' is your preferences alone."
            ),
        },
        "run_id": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "description": "Optional Claude Code session ID. Restricts the search to memories written from that session.",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}


class ToolInputError(ValueError):
    pass


def _validate_arguments(
    arguments: Any,
) -> tuple[str, int | None, str | None, str | None, str | None]:
    if not isinstance(arguments, dict):
        raise ToolInputError("Search arguments must be an object.")

    unknown = set(arguments) - {"query", "top_k", "category", "scope", "run_id"}
    if unknown:
        raise ToolInputError(f"Unknown search argument: {sorted(unknown)[0]}")

    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolInputError("query must be a non-empty string.")
    query = query.strip()
    if len(query) > 2000:
        raise ToolInputError("query must be at most 2,000 characters.")

    top_k = arguments.get("top_k")
    if top_k is not None and (
        isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20
    ):
        raise ToolInputError("top_k must be an integer from 1 to 20.")

    category = arguments.get("category")
    if category is not None and category not in CODING_MEMORY_CATEGORY_NAMES:
        raise ToolInputError("category must be one of Mem0's supported categories.")

    scope = arguments.get("scope")
    if scope is not None and scope not in SEARCH_SCOPES:
        raise ToolInputError(f"scope must be one of {list(SEARCH_SCOPES)}.")

    run_id = arguments.get("run_id")
    if run_id is not None and (
        not isinstance(run_id, str) or not run_id.strip() or len(run_id) > 200
    ):
        raise ToolInputError("run_id must be a non-empty string of at most 200 characters.")
    return query, top_k, category, scope, run_id


def call_search_memories(arguments: Any) -> str:
    query, top_k, category, scope, run_id = _validate_arguments(arguments)
    repo = resolve_repo(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    result = search_memories(
        None,
        repo,
        None,
        query,
        top_k=top_k,
        category=category,
        scope=scope,
        run_id=run_id,
        operation="mcp-search",
    )
    return format_search_result(result)


def _tool_response(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def handle_request(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return None
    request_id = message.get("id")
    method = message.get("method")

    if method == "notifications/initialized":
        return None
    if method == "initialize":
        requested = (message.get("params") or {}).get("protocolVersion")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": requested or PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mem0", "version": "0.3.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": TOOL_NAME,
                        "description": TOOL_DESCRIPTION,
                        "inputSchema": TOOL_SCHEMA,
                        "annotations": {
                            "readOnlyHint": True,
                            "idempotentHint": True,
                            "openWorldHint": True,
                        },
                    }
                ]
            },
        }
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != TOOL_NAME:
            result = _tool_response("Unknown Mem0 tool.", is_error=True)
        else:
            try:
                result = _tool_response(call_search_memories(params.get("arguments")))
            except ToolInputError as exc:
                result = _tool_response(str(exc), is_error=True)
            except Exception:
                result = _tool_response("Memory search failed.", is_error=True)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


def main() -> int:
    for raw_line in sys.stdin:
        try:
            message = json.loads(raw_line)
            response = handle_request(message)
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        except Exception:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": "Internal error"},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    telemetry.spawn_flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
