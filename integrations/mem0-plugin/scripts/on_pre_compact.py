#!/usr/bin/env python3
"""Capture session state via the Mem0 REST API.

Safety net for PreCompact and Stop hooks — reads the transcript JSONL,
extracts structured session state, and stores it in Mem0 directly.

Used by:
  - PreCompact hook: Tags with "pre-compaction" (context about to be lost)
  - Stop hook:       Tags with "session-end" (session ending, Claude can't respond)

Input:  JSON on stdin with transcript_path, session_id, cwd
Output: stderr logs only (exit 0 always — must not block)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api import add_memory
from _identity import resolve_api_key, resolve_user_id
from _project import resolve_branch, resolve_project_id

log = logging.getLogger("mem0-capture")
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("[mem0-capture] %(message)s"))
log.addHandler(_handler)

if os.environ.get("MEM0_DEBUG"):
    _log_dir = os.path.expanduser("~/.mem0")
    try:
        os.makedirs(_log_dir, exist_ok=True)
        _file_handler = logging.FileHandler(os.path.join(_log_dir, "hooks.log"))
        _file_handler.setFormatter(logging.Formatter("[mem0-capture] %(asctime)s %(message)s"))
        log.addHandler(_file_handler)
    except OSError:
        pass

MAX_TAIL_LINES = 500
MAX_USER_MESSAGES = 30
MAX_BASH_COMMANDS = 20
MAX_ASSISTANT_TEXT = 10000
# session_state captures churn fast (active codebase, files in flight). Past
# ~3 months they're stale noise. Durable facts (decisions, conventions) are
# stored separately by the agent without an expiration_date.
SESSION_STATE_EXPIRY_DAYS = 90


def tail_lines(filepath: str, n: int) -> list[str]:
    """Read last n lines of a file efficiently."""
    try:
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            if file_size == 0:
                return []
            chunk_size = min(file_size, n * 4096)
            f.seek(max(0, file_size - chunk_size))
            data = f.read().decode("utf-8", errors="replace")
            return data.splitlines()[-n:]
    except OSError:
        return []


def parse_transcript(lines: list[str]) -> dict:
    """Parse transcript JSONL lines and extract session state."""
    user_messages: list[str] = []
    files_modified: set[str] = set()
    bash_commands: list[str] = []
    last_assistant_text = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        entry_type = entry.get("type")
        if entry_type not in ("user", "assistant"):
            continue
        if entry.get("isSidechain"):
            continue

        message = entry.get("message", {})
        content_blocks = message.get("content", [])

        if entry_type == "user":
            parts = []
            if isinstance(content_blocks, str):
                parts.append(content_blocks)
            elif isinstance(content_blocks, list):
                for block in content_blocks:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
            text = "\n".join(parts).strip()
            if text and len(text) > 10 and not text.startswith("<"):
                user_messages.append(text)

        elif entry_type == "assistant":
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = block.get("text", "").strip()
                    if text:
                        last_assistant_text = text
                if block.get("type") == "tool_use":
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})
                    if tool_name in ("Write", "Edit"):
                        fp = tool_input.get("file_path", "")
                        if fp:
                            files_modified.add(fp)
                    elif tool_name == "Bash":
                        cmd = tool_input.get("command", "")
                        if cmd:
                            bash_commands.append(cmd)

    return {
        "user_messages": user_messages[-MAX_USER_MESSAGES:],
        "files_modified": sorted(files_modified),
        "bash_commands": bash_commands[-MAX_BASH_COMMANDS:],
        "last_assistant_text": last_assistant_text[:MAX_ASSISTANT_TEXT],
    }


def build_content(state: dict, source: str) -> str:
    """Build minimal context — only what's needed to resume work.

    This is a FALLBACK safety net, not the primary capture path.
    The agent handles rich memory storage via on_pre_compact.sh prompts.
    This script only fires when the agent didn't store enough on its own.

    Keep it short — mem0 infer=True will extract structured facts.
    """
    parts = []

    if state["files_modified"]:
        parts.append(f"Files touched: {', '.join(state['files_modified'][:15])}")

    if state["bash_commands"]:
        git_cmds = [c for c in state["bash_commands"] if "git " in c]
        if git_cmds:
            parts.append(f"Git operations: {len(git_cmds)}")

    return "\n".join(parts)


def store_memory(api_key: str, content: str, user_id: str, source: str, session_id: str = "", project_id: str = "", branch: str = "") -> bool:
    """Store session state as a memory via the Mem0 REST API."""
    expires = (date.today() + timedelta(days=SESSION_STATE_EXPIRY_DAYS)).isoformat()
    metadata = {
        "type": "session_state",
        "source": source,
        "session_id": session_id,
    }
    if branch:
        metadata["branch"] = branch
    body = {
        "messages": [
            {"role": "user", "content": content}
        ],
        "user_id": user_id,
        "app_id": project_id,
        "metadata": metadata,
        "expiration_date": expires,
        "infer": True,
    }

    try:
        status, _result = add_memory(api_key, body, timeout=15)
        if status in (200, 201):
            log.info("Session state stored successfully")
            return True
        log.warning("API returned status %d", status)
        return False
    except urllib.error.URLError as e:
        log.warning("API call failed: %s", e)
        return False


def format_status(state: dict, source: str, stored: bool, skipped_reason: str = "") -> str:
    """Build a clean, readable status line for terminal display."""
    files_count = len(state.get("files_modified", []))
    git_cmds = [c for c in state.get("bash_commands", []) if "git " in c]
    user_msgs = len(state.get("user_messages", []))

    parts = []
    if files_count:
        parts.append(f"{files_count} file{'s' if files_count != 1 else ''} touched")
    if git_cmds:
        parts.append(f"{len(git_cmds)} git op{'s' if len(git_cmds) != 1 else ''}")
    if user_msgs:
        parts.append(f"{user_msgs} exchange{'s' if user_msgs != 1 else ''}")

    activity = ", ".join(parts) if parts else "minimal activity"

    if source == "pre-compaction":
        icon = "✨"  # ✨
        label = "Pre-compaction snapshot"
    else:
        icon = "\U0001f4be"  # 💾
        label = "Session-end snapshot"

    if skipped_reason:
        return f"{icon} Mem0 {label} — {activity} — {skipped_reason}"
    elif stored:
        return f"{icon} Mem0 {label} — {activity} — saved to mem0"
    else:
        return f"{icon} Mem0 {label} — {activity} — nothing to capture"


def main():
    source = "pre-compaction"
    show_status = False
    for arg in sys.argv[1:]:
        if arg.startswith("--source="):
            source = arg.split("=", 1)[1]
        elif arg == "--status":
            show_status = True

    api_key = resolve_api_key()
    if not api_key:
        log.debug("MEM0_API_KEY not set, skipping capture")
        if show_status:
            print("✨ Mem0 — no API key, skipping capture")
        return

    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        log.debug("No valid JSON on stdin")
        return

    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path:
        log.debug("No transcript_path provided")
        return

    session_id = hook_input.get("session_id", "")
    cwd = hook_input.get("cwd") or None
    user_id = resolve_user_id()
    project_id = resolve_project_id(cwd)
    branch = resolve_branch(cwd)

    lines = tail_lines(transcript_path, MAX_TAIL_LINES)
    if not lines:
        log.debug("Transcript empty or unreadable: %s", transcript_path)
        return

    state = parse_transcript(lines)

    # Skip if agent already stored memories this session — avoid duplicate writes.
    stats_file = f"/tmp/mem0_session_stats_{os.environ.get('USER', 'default')}.json"
    try:
        with open(stats_file) as f:
            stats = json.load(f)
        if stats.get("adds", 0) >= 1:
            log.info("Agent stored %d memories this session — skipping fallback", stats["adds"])
            if show_status:
                print(format_status(state, source, False, f"agent already stored {stats['adds']} memor{'ies' if stats['adds'] != 1 else 'y'}"))
            return
    except (OSError, json.JSONDecodeError):
        pass

    if not state["files_modified"]:
        log.debug("No files modified — skipping fallback capture")
        if show_status:
            print(format_status(state, source, False))
        return

    content = build_content(state, source)
    if not content.strip():
        log.debug("No content to store")
        if show_status:
            print(format_status(state, source, False))
        return

    log.info("Fallback capture: %d files modified", len(state["files_modified"]))
    stored = store_memory(api_key, content, user_id, source, session_id, project_id, branch)

    if show_status:
        print(format_status(state, source, stored))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error("Unexpected error: %s", e)
    sys.exit(0)
