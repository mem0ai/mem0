"""Shared mem0 search API helper.

Wraps POST /v3/memories/search/ into a single function call.
All pre-fetch hooks use this instead of duplicating urllib boilerplate.
"""

from __future__ import annotations

import json
import urllib.request

SEARCH_URL = "https://api.mem0.ai/v3/memories/search/"
SEARCH_TIMEOUT = 5


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

    filters: dict = {"AND": [{"user_id": user_id}, {"app_id": project_id}]}
    if metadata_type:
        filters["AND"].append({"metadata": {"type": metadata_type}})
    if metadata_filters:
        for key, value in metadata_filters.items():
            filters["AND"].append({"metadata": {key: value}})

    payload: dict = {"query": query, "filters": filters, "top_k": top_k, "threshold": threshold}
    if rerank:
        payload["rerank"] = True
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        SEARCH_URL,
        data=body,
        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as r:
            data = json.loads(r.read())
            results = data if isinstance(data, list) else data.get("results", [])
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
