#!/usr/bin/env python3
"""Capture the post-compaction summary into mem0.

PreCompact hooks fire BEFORE the summary is generated, so they can't
store the actual compact-summary text. This script runs at
SessionStart with source=compact, reads the transcript, finds the
most recent entry flagged isCompactSummary=true, and stores it as a
memory tagged metadata.type=compact_summary.

Input:  JSON on stdin with transcript_path, session_id, source
Output: stderr logs only (exit 0 always -- must not block)

Spawned in the background by on_session_start.sh; the user-facing
bootstrap text continues without waiting on the network.
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

log = logging.getLogger("mem0-compact-summary")
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("[mem0-compact-summary] %(message)s"))
log.addHandler(_handler)

if os.environ.get("MEM0_DEBUG"):
    _log_dir = os.path.expanduser("~/.mem0")
    try:
        os.makedirs(_log_dir, exist_ok=True)
        _file_handler = logging.FileHandler(os.path.join(_log_dir, "hooks.log"))
        _file_handler.setFormatter(logging.Formatter("[mem0-compact-summary] %(asctime)s %(message)s"))
        log.addHandler(_file_handler)
    except OSError:
        pass

API_URL = "https://api.mem0.ai"
MAX_TAIL_LINES = 2000
MAX_SUMMARY_CHARS = 50000
# Compact summaries describe a single session's state -- stale after a quarter.
COMPACT_SUMMARY_EXPIRY_DAYS = 90


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


def find_compact_summary(lines: list[str]) -> str:
    """Walk transcript backwards, return text content of the most recent
    entry flagged isCompactSummary=true. Empty string if none found."""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not entry.get("isCompactSummary"):
            continue

        message = entry.get("message", {})
        content = message.get("content", [])
        if isinstance(content, str):
            return content[:MAX_SUMMARY_CHARS]
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "\n".join(parts).strip()[:MAX_SUMMARY_CHARS]
    return ""


def store_summary(api_key: str, summary: str, user_id: str, session_id: str) -> bool:
    expires = (date.today() + timedelta(days=COMPACT_SUMMARY_EXPIRY_DAYS)).isoformat()
    body = {
        "messages": [{"role": "user", "content": summary}],
        "user_id": user_id,
        "metadata": {
            "type": "compact_summary",
            "source": "session-start-compact",
            "session_id": session_id,
        },
        "infer": False,
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
                log.info("Compact summary stored")
                return True
            log.warning("API returned status %d", resp.status)
            return False
    except urllib.error.URLError as e:
        log.warning("API call failed: %s", e)
        return False


def main():
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

    summary = find_compact_summary(lines)
    if not summary:
        log.debug("No isCompactSummary entry found")
        return

    log.info("Capturing compact summary (%d chars)", len(summary))
    store_summary(api_key, summary, user_id, session_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error("Unexpected error: %s", e)
    sys.exit(0)
