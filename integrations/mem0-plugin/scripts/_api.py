"""Translate memory API calls between the hosted Mem0 Platform and a self-hosted server.

The hosted Platform speaks versioned /v1 and /v3 paths, `Authorization: Token`
auth, and scopes writes/searches with a top-level app_id. The self-hosted OSS
server (server/) speaks unversioned /memories and /search paths, `X-API-Key`
auth, and has no app_id concept -- agent_id is the closest first-class
scoping dimension there. Every helper below branches on resolve_base_url().
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from _identity import DEFAULT_BASE_URL, resolve_base_url

FETCH_TIMEOUT = 5
SELF_HOSTED_COUNT_CAP = 100


def is_self_hosted(base_url: str | None = None) -> bool:
    base_url = base_url if base_url is not None else resolve_base_url()
    return base_url.rstrip("/") != DEFAULT_BASE_URL


def auth_headers(api_key: str) -> dict[str, str]:
    if is_self_hosted():
        return {"X-API-Key": api_key}
    return {"Authorization": f"Token {api_key}"}


def project_field() -> str:
    """Body/filter key for project scoping: agent_id (self-hosted) or app_id (hosted Platform)."""
    return "agent_id" if is_self_hosted() else "app_id"


def add_url() -> str:
    base_url = resolve_base_url()
    if is_self_hosted(base_url):
        return f"{base_url}/memories"
    return f"{base_url}/v3/memories/add/"


def search_url() -> str:
    base_url = resolve_base_url()
    if is_self_hosted(base_url):
        return f"{base_url}/search"
    return f"{base_url}/v3/memories/search/"


def delete_url(memory_id: str) -> str:
    base_url = resolve_base_url()
    if is_self_hosted(base_url):
        return f"{base_url}/memories/{memory_id}"
    return f"{base_url}/v1/memories/{memory_id}/"


def fetch_recent(api_key: str, user_id: str, project_id: str, top_k: int = 1, global_search: bool = False) -> list:
    """Fetch recent memories for a scope. Returns [] on any error; never raises.

    Hosted Platform lists via POST with an AND/OR filters body. The self-hosted
    server has no such endpoint -- it only supports GET /memories with flat
    user_id/agent_id/top_k query params, so global (cross-user) listing there
    is best-effort and may return nothing if the caller lacks admin rights.
    """
    base_url = resolve_base_url()
    headers = auth_headers(api_key)
    try:
        if is_self_hosted(base_url):
            headers = dict(headers)
            params = f"top_k={top_k}"
            if not global_search:
                params = f"user_id={user_id}&{project_field()}={project_id}&{params}"
            req = urllib.request.Request(f"{base_url}/memories?{params}", headers=headers, method="GET")
        else:
            if global_search:
                filters = {"OR": [{"user_id": "*"}]}
            else:
                filters = {"AND": [{"user_id": user_id}, {project_field(): project_id}]}
            body = json.dumps({"filters": filters}).encode()
            headers = dict(headers)
            headers["Content-Type"] = "application/json"
            req = urllib.request.Request(
                f"{base_url}/v3/memories/?page=1&page_size={top_k}", data=body, headers=headers, method="POST"
            )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            data = json.loads(r.read())
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("results", [])
        return []
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return []


def count_memories(api_key: str, user_id: str, project_id: str, global_search: bool = False) -> str:
    """Total memory count for a scope, as a string ("?" on any error).

    Hosted Platform's list endpoint reports a true total in its `count` field
    even with page_size=1. The self-hosted server has no such total, so its
    count is a best-effort len() over a capped GET (accurate up to SELF_HOSTED_COUNT_CAP).
    """
    base_url = resolve_base_url()
    headers = auth_headers(api_key)
    try:
        if is_self_hosted(base_url):
            params = f"top_k={SELF_HOSTED_COUNT_CAP}"
            if not global_search:
                params = f"user_id={user_id}&{project_field()}={project_id}&{params}"
            req = urllib.request.Request(f"{base_url}/memories?{params}", headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
                data = json.loads(r.read())
            results = data.get("results", []) if isinstance(data, dict) else data
            return str(len(results)) if isinstance(results, list) else "?"

        if global_search:
            filters = {"OR": [{"user_id": "*"}]}
        else:
            filters = {"AND": [{"user_id": user_id}, {project_field(): project_id}]}
        body = json.dumps({"filters": filters}).encode()
        headers = {**headers, "Content-Type": "application/json"}
        req = urllib.request.Request(
            f"{base_url}/v3/memories/?page=1&page_size=1", data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            data = json.loads(r.read())
        if isinstance(data, dict) and "count" in data:
            return str(data["count"])
        if isinstance(data, list):
            return str(len(data))
        return "?"
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return "?"
