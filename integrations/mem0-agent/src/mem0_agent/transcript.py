"""Read editor transcripts into conversational windows.

Hooks hand us a JSONL transcript path. A "window" is the recent stretch of natural
conversation -- user and assistant text only. Tool call/result entries are kept out of
the window content but counted, so the trigger rules can recognise a tool-only turn.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_TURN_CHARS = 4000
DEFAULT_TAIL = 400


def _content_text(content: Any) -> tuple[str, bool]:
    """Returns (text, saw_tool_block)."""
    if isinstance(content, str):
        return content, False
    if not isinstance(content, list):
        return "", False
    parts, tool = [], False
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text" and block.get("text"):
            parts.append(str(block["text"]))
        elif btype in ("tool_use", "tool_result", "thinking"):
            tool = True
    return "\n".join(parts), tool


def read_turns(path: str | Path, tail: int = DEFAULT_TAIL) -> list[dict]:
    """Parse the last `tail` transcript lines into {role, content, tool_only} turns."""
    try:
        lines = Path(path).read_text(errors="replace").splitlines()[-tail:]
    except Exception:
        return []

    turns: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("isSidechain") or entry.get("isMeta"):
            continue  # subagent / bookkeeping entries are never memory candidates
        msg = entry.get("message")
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        text, saw_tool = _content_text(msg.get("content"))
        text = text.strip()
        if not text and not saw_tool:
            continue
        turns.append({
            "role": role,
            "content": text[:MAX_TURN_CHARS],
            "tool_only": bool(saw_tool and not text),
        })
    return turns


def latest_window(turns: list[dict], size: int = 4) -> list[dict]:
    """The most recent exchange: up to `size` turns ending at the last assistant reply."""
    if not turns:
        return []
    return turns[-size:]


def windows_since(turns: list[dict], processed: int, size: int = 4) -> list[list[dict]]:
    """Non-overlapping windows for turns we have not classified yet.

    v1 re-sent overlapping windows every third message and relied on the platform to
    deduplicate; this advances a cursor instead.
    """
    fresh = turns[processed:]
    return [fresh[i:i + size] for i in range(0, len(fresh), size) if fresh[i:i + size]]


MIN_THREAD_WORDS = 4


def _signal_turns(turns: list[dict]) -> list[dict]:
    """Drop the same mechanical noise the capture gate drops.

    Without this the open-thread snapshot fills up with progress lines and
    "I modified VERSION, cli.py, ..." -- the exact content the audit found made v1's
    session summaries worthless.
    """
    from .triggers import _turn_drop_reason, natural_words

    kept = []
    for t in turns:
        if t.get("tool_only") or not t.get("content"):
            continue
        if _turn_drop_reason([t]):
            continue
        if natural_words(t["content"]) < MIN_THREAD_WORDS:
            continue  # "ok", "good catch" -- acknowledgements, not state
        kept.append(t)
    return kept


def summarize_open_thread(turns: list[dict], limit: int = 3) -> str:
    """A plain-language snapshot for session_state: what we were doing, where it stopped."""
    signal = _signal_turns(turns)
    users = [t["content"] for t in signal if t["role"] == "user"]
    assistants = [t["content"] for t in signal if t["role"] == "assistant"]
    if not users and not assistants:
        return ""
    goal = users[0][:300] if users else ""
    latest = users[-1][:300] if users else ""
    last_reply = assistants[-1][:300] if assistants else ""
    bits = []
    if goal:
        bits.append(f"Working on: {goal}")
    if latest and latest != goal:
        bits.append(f"Most recent request: {latest}")
    if last_reply:
        bits.append(f"Left off: {last_reply}")
    return " | ".join(bits[:limit])
