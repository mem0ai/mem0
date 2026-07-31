"""Transport adapter for Mem0 Platform and self-hosted REST APIs.

The plugin keeps its existing Platform behaviour unless ``MEM0_API_BASE`` is
set. In self-hosted mode, hosted ``app_id`` scopes are translated to the
self-hosted server's equivalent ``agent_id`` scope.

This module intentionally uses only the Python standard library because hook
scripts must work before the plugin's optional virtual environment is ready.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

PLATFORM_API_BASE = "https://api.mem0.ai"
DEFAULT_TIMEOUT = 15


def is_self_hosted() -> bool:
    """Return whether hooks should use a self-hosted Mem0 REST server."""
    return bool(os.environ.get("MEM0_API_BASE", "").strip())


def api_base_url() -> str:
    """Return the selected API base URL without a trailing slash."""
    configured = os.environ.get("MEM0_API_BASE", "").strip()
    return (configured or PLATFORM_API_BASE).rstrip("/")


def auth_headers(api_key: str) -> dict[str, str]:
    """Build authentication headers for the selected backend."""
    if is_self_hosted():
        return {"X-API-Key": api_key}
    return {"Authorization": f"Token {api_key}"}


def _request_json(
    api_key: str,
    path: str,
    *,
    method: str,
    body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, Any]:
    """Send one JSON request and return ``(status, decoded_body)``."""
    url = f"{api_base_url()}{path}"
    filtered_query = {key: value for key, value in (query or {}).items() if value is not None}
    if filtered_query:
        url = f"{url}?{urllib.parse.urlencode(filtered_query)}"

    encoded_body = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=encoded_body,
        headers={"Content-Type": "application/json", **auth_headers(api_key)},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        read = getattr(response, "read", None)
        if not callable(read):
            return response.status, {}
        raw = read()
        if not raw or not isinstance(raw, (bytes, bytearray, str)):
            return response.status, {}
        return response.status, json.loads(raw)


def _map_scope(value: Any) -> Any:
    """Recursively translate hosted ``app_id`` scopes to ``agent_id``."""
    if isinstance(value, list):
        return [_map_scope(item) for item in value]
    if not isinstance(value, dict):
        return value

    mapped: dict[str, Any] = {}
    for key, item in value.items():
        mapped["agent_id" if key == "app_id" else key] = _map_scope(item)
    return mapped


def _map_add_payload(payload: dict[str, Any]) -> dict[str, Any]:
    mapped = dict(payload)
    app_id = mapped.pop("app_id", None)
    if app_id and not mapped.get("agent_id"):
        mapped["agent_id"] = app_id
    return mapped


def add_memory(
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, Any]:
    """Add memories using the selected backend."""
    if is_self_hosted():
        return _request_json(
            api_key,
            "/memories",
            method="POST",
            body=_map_add_payload(payload),
            timeout=timeout,
        )
    return _request_json(api_key, "/v3/memories/add/", method="POST", body=payload, timeout=timeout)


def search_memories(
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout: int = 5,
) -> tuple[int, Any]:
    """Search memories using the selected backend."""
    if is_self_hosted():
        mapped = _map_scope(payload)
        mapped.pop("rerank", None)  # The self-hosted endpoint does not expose hosted reranking.
        return _request_json(api_key, "/search", method="POST", body=mapped, timeout=timeout)
    return _request_json(api_key, "/v3/memories/search/", method="POST", body=payload, timeout=timeout)


def list_memories(
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout: int = 5,
) -> tuple[int, Any]:
    """List memories, normalizing hosted filters for the self-hosted API."""
    if not is_self_hosted():
        page = payload.get("page", 1)
        page_size = payload.get("page_size") or payload.get("top_k") or 10
        return _request_json(
            api_key,
            f"/v3/memories/?page={page}&page_size={page_size}",
            method="POST",
            body={"filters": payload.get("filters") or {}},
            timeout=timeout,
        )

    filters = _map_scope(payload.get("filters") or {})
    query: dict[str, Any] = {
        "top_k": payload.get("page_size") or payload.get("top_k"),
        "show_expired": payload.get("show_expired"),
    }
    clauses = filters.get("AND", []) if isinstance(filters, dict) else []
    if not clauses and isinstance(filters, dict):
        clauses = [filters]
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        for key in ("user_id", "agent_id", "run_id"):
            value = clause.get(key)
            if isinstance(value, str) and value != "*":
                query[key] = value

    return _request_json(api_key, "/memories", method="GET", query=query, timeout=timeout)


def delete_memory(api_key: str, memory_id: str, *, timeout: int = 10) -> tuple[int, Any]:
    """Delete one memory using the selected backend."""
    safe_id = urllib.parse.quote(memory_id, safe="")
    path = f"/memories/{safe_id}" if is_self_hosted() else f"/v1/memories/{safe_id}/"
    return _request_json(api_key, path, method="DELETE", timeout=timeout)
