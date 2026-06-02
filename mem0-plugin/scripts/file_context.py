#!/usr/bin/env python3
"""File-context injection for PreToolUse/Read hook.

When Claude is about to read a file, this script searches mem0 for
memories that reference that file path and returns a compact timeline
of prior work. This gives Claude context like "last time you fixed a
null pointer here" before it reads the file.

Modeled after claude-mem's file-context handler but adapted for mem0's
cloud API architecture.

Input:  file_path (positional arg), env vars for identity
Output: JSON to stdout with hookSpecificOutput.additionalContext
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _formatting import TYPE_ICONS, format_age
from _identity import resolve_api_key, resolve_user_id
from _project import resolve_project_id
from _search import search_memories

FILE_READ_GATE_MIN_BYTES = 1500
MAX_RESULTS = 5
SEARCH_TIMEOUT = 5


def gate_file(file_path: str, cwd: str) -> str | None:
    """Return the resolved absolute path if the file passes gating, else None."""
    if not file_path:
        return None
    p = Path(file_path)
    if not p.is_absolute():
        p = Path(cwd) / p
    try:
        p = p.resolve()
        if not p.is_file():
            return None
        if p.stat().st_size < FILE_READ_GATE_MIN_BYTES:
            return None
        return str(p)
    except OSError:
        return None


def relative_path(abs_path: str, cwd: str) -> str:
    try:
        return os.path.relpath(abs_path, cwd)
    except ValueError:
        return abs_path


def format_timeline(memories: list[dict], file_path: str) -> str:
    """Format memories into a compact timeline for context injection."""
    if not memories:
        return ""

    rel = file_path
    lines = [
        f"Prior work on `{rel}` — {len(memories)} memories found.",
        "Need details? Use `search_memories` with the memory ID.",
        "",
    ]

    for m in memories:
        mid = m.get("id", "?")[:8]
        text = (m.get("memory", "") or "")[:150].replace("\n", " ").strip()
        meta = m.get("metadata") or {}
        cat = meta.get("type", "unknown")
        icon = TYPE_ICONS.get(cat, "❓")
        age = format_age(m)
        age_str = f" ({age})" if age else ""
        lines.append(f"- {icon} [{cat}]{age_str} {text} [mem0:{mid}]")

    return "\n".join(lines)


def search_file_context(
    api_key: str, user_id: str, project_id: str, file_path: str, cwd: str
) -> str:
    """Search mem0 for memories related to a file path."""
    global_search = os.environ.get("MEM0_GLOBAL_SEARCH", "false") == "true"
    rel = relative_path(file_path, cwd)
    basename = os.path.basename(file_path)

    query = f"{rel} {basename}" if rel != basename else rel
    results = search_memories(
        api_key, user_id, project_id, query,
        top_k=MAX_RESULTS, threshold=0.3,
        global_search=global_search,
    )

    results = results[:MAX_RESULTS]

    return format_timeline(results, rel)


def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    file_path = sys.argv[1]
    cwd = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    api_key = resolve_api_key()
    if not api_key:
        sys.exit(0)

    resolved = gate_file(file_path, cwd)
    if not resolved:
        sys.exit(0)

    user_id = resolve_user_id()
    project_id = resolve_project_id(cwd)

    timeline = search_file_context(api_key, user_id, project_id, resolved, cwd)
    if not timeline:
        sys.exit(0)

    print(timeline, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
