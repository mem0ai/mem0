#!/usr/bin/env python3
"""Session stats tracker for mem0 plugin.

Tracks memory adds/searches per session.
Uses /tmp/mem0_session_stats_$USER.json (single file per user, reset on init).

Usage:
  python session_stats.py init            # reset for new session
  python session_stats.py add <category>  # record a memory write
  python session_stats.py search          # record a search
  python session_stats.py report          # print summary, clean up temp file
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

STATS_FILE = f"/tmp/mem0_session_stats_{os.environ.get('USER', 'default')}.json"


def _load() -> dict:
    if os.path.isfile(STATS_FILE):
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "adds": 0,
        "searches": 0,
        "categories": [],
        "category_counts": {},
        "started": datetime.now().isoformat(),
    }


def _save(stats: dict) -> None:
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f)


MAX_RECENT_IDS = 50


def init() -> None:
    _save({
        "adds": 0,
        "searches": 0,
        "categories": [],
        "category_counts": {},
        "recent_ids": [],
        "started": datetime.now().isoformat(),
    })


def record_add(category: str = "", memory_id: str = "") -> None:
    stats = _load()
    stats["adds"] = stats.get("adds", 0) + 1
    if category:
        if category not in stats.get("categories", []):
            stats.setdefault("categories", []).append(category)
        counts = stats.setdefault("category_counts", {})
        counts[category] = counts.get(category, 0) + 1
    if memory_id:
        recent = stats.setdefault("recent_ids", [])
        recent.append({"id": memory_id, "category": category, "ts": datetime.now().isoformat()})
        if len(recent) > MAX_RECENT_IDS:
            stats["recent_ids"] = recent[-MAX_RECENT_IDS:]
    _save(stats)


def record_search() -> None:
    stats = _load()
    stats["searches"] = stats.get("searches", 0) + 1
    _save(stats)


def peek() -> str:
    """Return current stats as JSON without clearing the file."""
    stats = _load()
    return json.dumps(stats)


def report() -> str:
    stats = _load()
    adds = stats.get("adds", 0)
    searches = stats.get("searches", 0)
    categories = stats.get("categories", [])

    # Clean up temp file after reading
    try:
        os.unlink(STATS_FILE)
    except OSError:
        pass

    if adds == 0 and searches == 0:
        return ""

    parts = []
    parts.append(f"Session: wrote {adds} memories, retrieved {searches}")
    if categories:
        parts.append(f"Categories touched: {', '.join(categories)}")

    return ". ".join(parts) + "."


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: session_stats.py [init|add|search|report]", file=sys.stderr)
        return 1

    cmd = sys.argv[1]
    if cmd == "init":
        init()
    elif cmd == "add":
        category = sys.argv[2] if len(sys.argv) > 2 else ""
        memory_id = sys.argv[3] if len(sys.argv) > 3 else ""
        record_add(category, memory_id)
    elif cmd == "search":
        record_search()
    elif cmd == "peek":
        print(peek())
    elif cmd == "report":
        result = report()
        if result:
            print(result)
        else:
            print("Session: no memory operations.")
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
