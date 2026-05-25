#!/usr/bin/env python3
"""Decide whether the Stop hook should block, and build context for Claude.

Reads the transcript to determine if meaningful work happened.
Outputs JSON: {"should_block": bool, "context": "..."}.

Called by on_stop.sh with the hook input JSON on stdin.
"""

from __future__ import annotations

import json
import sys

MAX_TAIL_LINES = 500
MAX_USER_MESSAGES = 30
MAX_BASH_COMMANDS = 20


def tail_lines(filepath: str, n: int) -> list[str]:
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
    user_messages: list[str] = []
    files_modified: set[str] = set()
    bash_commands: list[str] = []
    tool_calls: int = 0

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
                user_messages.append(text[:300])

        elif entry_type == "assistant":
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    tool_calls += 1
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})
                    if tool_name in ("Write", "Edit"):
                        fp = tool_input.get("file_path", "")
                        if fp:
                            files_modified.add(fp)
                    elif tool_name == "Bash":
                        cmd = tool_input.get("command", "")
                        if cmd:
                            bash_commands.append(cmd[:200])

    return {
        "user_messages": user_messages[-MAX_USER_MESSAGES:],
        "files_modified": sorted(files_modified),
        "bash_commands": bash_commands[-MAX_BASH_COMMANDS:],
        "tool_calls": tool_calls,
    }


def should_block(state: dict) -> bool:
    if state["files_modified"]:
        return True
    if state["tool_calls"] >= 3:
        return True
    git_commands = [c for c in state["bash_commands"] if "git " in c]
    if git_commands:
        return True
    return False


def build_context(state: dict) -> str:
    parts = []

    if state["files_modified"]:
        files = state["files_modified"][:10]
        parts.append(f"Files modified this session: {', '.join(files)}")

    git_commits = [c for c in state["bash_commands"] if "git commit" in c]
    if git_commits:
        parts.append(f"Git commits made: {len(git_commits)}")

    if state["user_messages"]:
        tasks = []
        for msg in state["user_messages"][-5:]:
            first_line = msg.split("\n")[0][:150]
            tasks.append(f"  - {first_line}")
        parts.append("User requests:\n" + "\n".join(tasks))

    return "\n".join(parts)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        json.dump({"should_block": False, "context": ""}, sys.stdout)
        return

    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path:
        json.dump({"should_block": False, "context": ""}, sys.stdout)
        return

    lines = tail_lines(transcript_path, MAX_TAIL_LINES)
    if not lines:
        json.dump({"should_block": False, "context": ""}, sys.stdout)
        return

    state = parse_transcript(lines)
    block = should_block(state)
    context = build_context(state) if block else ""

    json.dump({"should_block": block, "context": context}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        json.dump({"should_block": False, "context": ""}, sys.stdout)
