#!/usr/bin/env python3
"""Translate Antigravity hooks into the shared Mem0 runtime."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
BUNDLED_CORE = HERE.parent.parent / "core"
CORE = BUNDLED_CORE if BUNDLED_CORE.is_dir() else HERE.parents[2] / "core" / "python"
sys.path.insert(0, str(CORE))

import hook_runner  # noqa: E402
import telemetry  # noqa: E402
from memory_core import configure_harness, record_tool  # noqa: E402


def normalize(payload: dict) -> dict:
    value = dict(payload)
    value.setdefault("session_id", value.get("conversationId", ""))
    workspaces = value.get("workspacePaths") or []
    if workspaces:
        value.setdefault("cwd", workspaces[0])
    value.setdefault("transcript_path", value.get("transcriptPath", ""))
    tool_call = value.get("toolCall") or {}
    if isinstance(tool_call, dict):
        value.setdefault("tool_name", tool_call.get("name", ""))
        value.setdefault("tool_input", tool_call.get("args", {}))
    if value.get("error"):
        value.setdefault("tool_response", value["error"])
    return value


def _record_failure(store, payload):
    return record_tool(store, payload, failed=True)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"PreInvocation", "PostToolUse", "Stop"}:
        return 2
    event = sys.argv[1]
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        raw = {}
    payload = normalize(raw if isinstance(raw, dict) else {})
    if event == "PreInvocation" and payload.get("invocationNum") != 0:
        print(json.dumps({"injectSteps": []}))
        return 0
    action = {
        "PreInvocation": ["session-start"],
        "PostToolUse": ["post-tool-failure" if payload.get("error") else "post-tool"],
        "Stop": ["flush", "--reason", "session-end"],
    }[event]
    sys.argv = [sys.argv[0], *action]
    sys.stdin = io.StringIO(json.dumps(payload))
    configure_harness("antigravity", data_dir_name="antigravity-plugin", source_tag="antigravity_plugin")
    telemetry.init(harness="antigravity", source_tag="ANTIGRAVITY_PLUGIN")
    with contextlib.redirect_stdout(io.StringIO()):
        result = hook_runner.run(
            extra_actions={"post-tool-failure": _record_failure},
            automatic_flush_reasons={"session-end"},
        )
    print(json.dumps({"injectSteps": []} if event == "PreInvocation" else ({"decision": "allow"} if event == "Stop" else {})))
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        hook_runner.log_failure(exc)
        print("{}")
        raise SystemExit(0) from None
