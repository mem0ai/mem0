#!/usr/bin/env python3
"""Fetch recent memories and format a compact timeline for SessionStart.

Searches mem0 cloud API for the most recent memories in the project
and formats them as a compact activity timeline injected below the
existing SessionStart banner.

Input:  env vars for identity (MEM0_API_KEY, MEM0_RESOLVED_USER_ID, etc.)
Output: Compact timeline text to stdout (empty if nothing found)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _formatting import TYPE_ICONS, format_age
from _identity import resolve_api_key, resolve_user_id
from _project import resolve_project_id

API_URL = "https://api.mem0.ai"
MAX_RECENT = 10
MAX_SUMMARIES = 3
FETCH_TIMEOUT = 5


def fetch_recent_memories(api_key: str, user_id: str, project_id: str) -> list[dict]:
    """Fetch the most recent memories for this project, sorted by recency."""
    body = {
        "filters": {"AND": [{"user_id": user_id}, {"app_id": project_id}]},
        "page": 1,
        "page_size": MAX_RECENT,
        "sort": "-created_at",
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API_URL}/v3/memories/",
        data=data,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            result = json.loads(r.read())
            if isinstance(result, dict) and "results" in result:
                return result["results"][:MAX_RECENT]
            if isinstance(result, list):
                return result[:MAX_RECENT]
            return []
    except Exception:
        return []


def format_timeline(memories: list[dict]) -> str:
    """Format memories into a compact recent activity timeline."""
    if not memories:
        return ""

    lines = ["### Recent Activity", ""]

    for m in memories:
        mid = m.get("id", "?")[:8]
        text = (m.get("memory", "") or "")[:120].replace("\n", " ").strip()
        meta = m.get("metadata") or {}
        cat = meta.get("type", "unknown")
        icon = TYPE_ICONS.get(cat, "❓")
        age = format_age(m)
        age_str = f" ({age})" if age else ""
        lines.append(f"- {icon} [{cat}]{age_str} {text} [mem0:{mid}]")

    lines.append("")
    lines.append("Search mem0 for details on any of these, or for past decisions and task learnings relevant to the current task.")

    return "\n".join(lines)


def main():
    api_key = resolve_api_key()
    if not api_key:
        return

    user_id = resolve_user_id()
    project_id = resolve_project_id(os.environ.get("MEM0_CWD"))

    memories = fetch_recent_memories(api_key, user_id, project_id)
    if not memories:
        return

    timeline = format_timeline(memories)
    if timeline:
        print(timeline, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
