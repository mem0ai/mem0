#!/usr/bin/env python3
"""Capture a structured session summary on Stop hook.

Runs on every Stop (end of each assistant turn). Each invocation reads
the transcript JSONL, extracts the latest assistant message and all
files touched so far, then stores via mem0 API with infer=True. Uses
run_id=session_id to scope infer dedup to the session, so the final
stored summary reflects the most recent turn — not just the first.

Input:  JSON on stdin with transcript_path, session_id, cwd, agent_id
Output: stderr logs only (exit 0 always — must not block)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _identity import resolve_api_key, resolve_config, resolve_user_id
from _project import resolve_branch, resolve_project_id

log = logging.getLogger("mem0-session-summary")
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("[mem0-session-summary] %(message)s"))
log.addHandler(_handler)

if os.environ.get("MEM0_DEBUG"):
    _log_dir = os.path.expanduser("~/.mem0")
    try:
        os.makedirs(_log_dir, exist_ok=True)
        _fh = logging.FileHandler(os.path.join(_log_dir, "hooks.log"))
        _fh.setFormatter(logging.Formatter("[mem0-session-summary] %(asctime)s %(message)s"))
        log.addHandler(_fh)
    except OSError:
        pass

API_URL = "https://api.mem0.ai"
MAX_TAIL_LINES = 3000
MAX_SUMMARY_CHARS = 50000
SUMMARY_EXPIRY_DAYS = 90

SYSTEM_TAG_RE = re.compile(
    r"<(?:system-reminder|private|claude-mem-context|persisted-output|system_instruction)>"
    r".*?"
    r"</(?:system-reminder|private|claude-mem-context|persisted-output|system_instruction)>",
    re.DOTALL,
)


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


def extract_last_assistant_message(lines: list[str]) -> str:
    """Walk transcript backwards, return text content of the last assistant message."""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        if '"type":"assistant"' not in line and '"type": "assistant"' not in line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message", {})
        content = message.get("content", [])
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "\n".join(parts).strip()
    return ""


def extract_files_touched(lines: list[str]) -> list[str]:
    """Extract unique file paths from tool_use content blocks in transcript."""
    files = set()
    file_ext_re = re.compile(
        r"[a-zA-Z0-9_./-]+\.(?:py|ts|tsx|js|jsx|rs|go|rb|java|sh|yaml|yml|json|toml|md|sql|css|html)"
    )
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if '"tool_use"' not in line and '"file_path"' not in line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            inp = block.get("input", {})
            if not isinstance(inp, dict):
                continue
            fp = inp.get("file_path", "")
            if fp:
                files.add(fp)
            command = inp.get("command", "")
            if command:
                for match in file_ext_re.findall(command):
                    files.add(match)
    return sorted(files)[:20]


def strip_tags(text: str) -> str:
    return SYSTEM_TAG_RE.sub("", text).strip()


def build_summary_prompt(assistant_msg: str, files: list[str]) -> str:
    """Build a structured prompt that helps mem0's AI extract a good summary."""
    files_section = ""
    if files:
        file_list = ", ".join(files[:10])
        files_section = f"\n\nFiles touched during this session: {file_list}"

    return (
        f"Session summary — store the following as a structured session summary.\n\n"
        f"What the assistant accomplished in this session:\n"
        f"{assistant_msg[:MAX_SUMMARY_CHARS]}"
        f"{files_section}\n\n"
        f"Extract and remember: what was requested, what was investigated, "
        f"key decisions made, what was completed, and what needs to happen next."
    )


def store_summary(
    api_key: str,
    summary_prompt: str,
    user_id: str,
    session_id: str,
    project_id: str,
    branch: str,
    files: list[str],
) -> bool:
    expires = (date.today() + timedelta(days=SUMMARY_EXPIRY_DAYS)).isoformat()
    metadata = {
        "type": "session_summary",
        "source": "stop-hook",
        "session_id": session_id,
    }
    if branch:
        metadata["branch"] = branch
    if files:
        metadata["files_touched"] = json.dumps(files[:20])

    body = {
        "messages": [{"role": "user", "content": summary_prompt}],
        "user_id": user_id,
        "app_id": project_id,
        "run_id": session_id,
        "metadata": metadata,
        "infer": True,
        "expiration_date": expires,
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/v3/memories/add/",
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
                log.info("Session summary stored")
                return True
            log.warning("API returned status %d", resp.status)
            return False
    except urllib.error.URLError as e:
        log.warning("API call failed: %s", e)
        return False


def main():
    api_key = resolve_api_key()
    if not api_key:
        log.debug("MEM0_API_KEY not set, skipping")
        return

    if not resolve_config().get("auto_save", True):
        log.debug("auto_save disabled, skipping")
        return

    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        log.debug("No valid JSON on stdin")
        return

    # Guard: skip subagent sessions (only root sessions get summaries)
    agent_id = hook_input.get("agent_id", "")
    if agent_id:
        log.debug("Subagent session (agent_id=%s), skipping", agent_id)
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

    assistant_msg = extract_last_assistant_message(lines)
    if not assistant_msg or len(assistant_msg.strip()) < 100:
        log.debug("Assistant message too short (%d chars) — skipping", len(assistant_msg.strip()))
        return

    assistant_msg = strip_tags(assistant_msg)
    files = extract_files_touched(lines)

    summary_prompt = build_summary_prompt(assistant_msg, files)

    log.info("Capturing session summary (%d chars, %d files)", len(assistant_msg), len(files))
    store_summary(api_key, summary_prompt, user_id, session_id, project_id, branch, files)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error("Unexpected error: %s", e)
    sys.exit(0)
