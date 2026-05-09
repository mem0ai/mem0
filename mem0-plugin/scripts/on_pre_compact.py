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
import urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _identity import resolve_user_id

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

API_URL = "https://api.mem0.ai"
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
    """Build structured markdown from parsed state."""
    parts = [f"## Session State ({source})\n"]

    if state["user_messages"]:
        parts.append("### What the user was working on")
        for msg in state["user_messages"]:
            truncated = msg[:5000] + "..." if len(msg) > 5000 else msg
            parts.append(f"- {truncated}")
        parts.append("")

    if state["files_modified"]:
        parts.append("### Files modified this session")
        for fp in state["files_modified"]:
            parts.append(f"- `{fp}`")
        parts.append("")

    if state["bash_commands"]:
        parts.append("### Recent commands")
        for cmd in state["bash_commands"]:
            truncated = cmd[:1000] + "..." if len(cmd) > 1000 else cmd
            parts.append(f"- `{truncated}`")
        parts.append("")

    if state["last_assistant_text"]:
        parts.append("### Last context")
        parts.append(state["last_assistant_text"])
        parts.append("")

    return "\n".join(parts)


def store_memory(api_key: str, content: str, user_id: str, source: str, session_id: str = "") -> bool:
    """Store session state as a memory via the Mem0 REST API."""
    expires = (date.today() + timedelta(days=SESSION_STATE_EXPIRY_DAYS)).isoformat()
    body = {
        "messages": [
            {"role": "user", "content": content}
        ],
        "user_id": user_id,
        "metadata": {
            "type": "session_state",
            "source": source,
            "session_id": session_id,
        },
        "expiration_date": expires,
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/v1/memories/",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Token {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                log.info("Session state stored successfully")
                return True
            log.warning("API returned status %d", resp.status)
            return False
    except urllib.error.URLError as e:
        log.warning("API call failed: %s", e)
        return False


def main():
    source = "pre-compaction"
    for arg in sys.argv[1:]:
        if arg.startswith("--source="):
            source = arg.split("=", 1)[1]

    api_key = os.environ.get("MEM0_API_KEY", "")
    if not api_key:
        log.debug("MEM0_API_KEY not set, skipping capture")
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
    user_id = resolve_user_id()

    lines = tail_lines(transcript_path, MAX_TAIL_LINES)
    if not lines:
        log.debug("Transcript empty or unreadable: %s", transcript_path)
        return

    state = parse_transcript(lines)
    if not state["user_messages"] and not state["files_modified"]:
        log.debug("No meaningful session state to capture")
        return

    content = build_content(state, source)

    log.info(
        "Capturing session state: %d user msgs, %d files, %d commands",
        len(state["user_messages"]),
        len(state["files_modified"]),
        len(state["bash_commands"]),
    )

    store_memory(api_key, content, user_id, source, session_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error("Unexpected error: %s", e)
    sys.exit(0)
