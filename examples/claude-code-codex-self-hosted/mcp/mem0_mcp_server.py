#!/usr/bin/env python3
"""MCP server exposing a self-hosted Mem0 REST API as native MCP tools.

This is the "explicit memory tools" entry point from the self-hosted
integration: agents (Claude Code, Codex, and anything else that speaks MCP)
get search/add/get/update/delete memory tools that forward to the local
self-hosted Mem0 REST API (``server/``, default http://localhost:8888).

Environment:
    MEM0_BASE_URL   Base URL of the self-hosted REST API (default http://localhost:8888)
    MEM0_API_KEY     API key created in the self-hosted dashboard (required)
    MEM0_USER_ID     Default user id (default "default")
    MEM0_AGENT_ID    Default agent id (default "default")

Run (stdio transport):
    pip install "mcp"
    MEM0_API_KEY=m0sk-... python mem0_mcp_server.py

Then register it in Claude Code (.mcp.json) or Codex (~/.codex/config.toml) —
see the README in this directory for the exact snippets.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mem0-self-hosted")

BASE_URL = os.environ.get("MEM0_BASE_URL", "http://localhost:8888").rstrip("/")
API_KEY = os.environ.get("MEM0_API_KEY", "")
USER_ID = os.environ.get("MEM0_USER_ID", "default")
AGENT_ID = os.environ.get("MEM0_AGENT_ID", "default")


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Forward a request to the self-hosted REST API and return parsed JSON."""
    if not API_KEY:
        return {"error": "MEM0_API_KEY is not set. Create an API key in the self-hosted dashboard."}
    url = f"{BASE_URL}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("X-API-Key", API_KEY)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        return {"error": f"Mem0 API returned {e.code}: {detail}"}
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach Mem0 API at {BASE_URL}: {e.reason}"}


@mcp.tool(
    description=(
        "Search through stored memories. This method is called whenever the user asks anything that "
        "might depend on past context, preferences, or previous decisions."
    )
)
def search_memories(query: str, user_id: str = USER_ID, agent_id: str = AGENT_ID) -> str:
    """Search memories relevant to a query, scoped to a user and agent."""
    payload = {"query": query, "filters": {"user_id": user_id, "agent_id": agent_id}, "top_k": 10}
    return json.dumps(_request("POST", "/search", payload), indent=2)


@mcp.tool(
    description=(
        "Add a new memory. Call this whenever the user shares a preference, fact, decision, or anything "
        "else worth remembering for future conversations. Set infer to False to store the text verbatim "
        "without LLM fact extraction."
    )
)
def add_memory(text: str, user_id: str = USER_ID, agent_id: str = AGENT_ID, infer: bool = True) -> str:
    """Store a new memory, optionally extracting facts from the raw text."""
    payload = {
        "messages": [{"role": "user", "content": text}],
        "user_id": user_id,
        "agent_id": agent_id,
        "infer": infer,
    }
    return json.dumps(_request("POST", "/memories", payload), indent=2)


@mcp.tool(description="List all memories stored for a user/agent.")
def get_memories(user_id: str = USER_ID, agent_id: str = AGENT_ID) -> str:
    """Retrieve stored memories for a user/agent scope."""
    path = f"/memories?user_id={urllib.request.quote(user_id)}&agent_id={urllib.request.quote(agent_id)}"
    return json.dumps(_request("GET", path), indent=2)


@mcp.tool(description="Update the text of an existing memory by its id.")
def update_memory(memory_id: str, text: str) -> str:
    """Replace the content of a stored memory."""
    path = f"/memories/{urllib.request.quote(memory_id)}"
    return json.dumps(_request("PUT", path, {"text": text}), indent=2)


@mcp.tool(description="Delete a specific memory by its id.")
def delete_memory(memory_id: str) -> str:
    """Delete a single stored memory."""
    path = f"/memories/{urllib.request.quote(memory_id)}"
    return json.dumps(_request("DELETE", path), indent=2)


if __name__ == "__main__":
    mcp.run()
