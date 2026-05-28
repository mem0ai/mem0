"""Shared mem0 search API helper.

Wraps POST /v3/memories/search/ into a single function call.
All pre-fetch hooks use this instead of duplicating urllib boilerplate.
"""

from __future__ import annotations

import json
import urllib.request

SEARCH_URL = "https://api.mem0.ai/v3/memories/search/"
SEARCH_TIMEOUT = 5


def _do_search(api_key: str, payload: dict) -> list[dict]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        SEARCH_URL,
        data=body,
        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as r:
        data = json.loads(r.read())
        return data if isinstance(data, list) else data.get("results", [])


def search_memories(
    api_key: str,
    user_id: str,
    project_id: str,
    query: str,
    metadata_type: str | None = None,
    metadata_filters: dict | None = None,
    top_k: int = 3,
    min_score: float = 0.0,
    rerank: bool = False,
    threshold: float = 0.3,
) -> list[dict]:
    if not api_key:
        return []

    base_clauses: list[dict] = [{"user_id": user_id}, {"app_id": project_id}]
    if metadata_type:
        base_clauses.append({"metadata": {"type": metadata_type}})
    if metadata_filters:
        for key, value in metadata_filters.items():
            base_clauses.append({"metadata": {key: value}})

    base_payload: dict = {"query": query, "top_k": top_k, "threshold": threshold}
    if rerank:
        base_payload["rerank"] = True

    try:
        payload = {**base_payload, "filters": {"AND": list(base_clauses)}}
        results = _do_search(api_key, payload)[:top_k]

        if min_score > 0:
            results = [m for m in results if m.get("score", 0) >= min_score]
        return results
    except Exception:
        return []


def format_results_for_context(
    memories: list[dict],
    heading: str = "Relevant memories",
) -> str:
    if not memories:
        return ""
    lines = [f"### {heading}", ""]
    for m in memories:
        mid = m.get("id", "?")[:8]
        text = m.get("memory", "")[:200]
        cat = (m.get("metadata") or {}).get("type", "unknown")
        lines.append(f"- [{cat}] {text} [mem0:{mid}]")
    lines.append("")
    return "\n".join(lines)
