#!/usr/bin/env python3
"""Translate Cursor's native hooks into the shared Mem0 runtime."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
BUNDLED_CORE = HERE.parent.parent / "core"
CORE = BUNDLED_CORE if BUNDLED_CORE.is_dir() else HERE.parents[2] / "core" / "python"
sys.path.insert(0, str(CORE))

import hook_runner  # noqa: E402
import telemetry  # noqa: E402
from memory_core import configure_harness, record_sidekick_start, record_sidekick_stop, record_tool  # noqa: E402

EVENTS = {
    "sessionStart": "session-start",
    "beforeSubmitPrompt": "user-prompt",
    "postToolUse": "post-tool",
    "postToolUseFailure": "post-tool-failure",
    "afterAgentResponse": "assistant-stop",
    "subagentStart": "sidekick-start",
    "subagentStop": "sidekick-stop",
    "stop": "stop",
    "sessionEnd": "session-end",
    "preCompact": "pre-compact",
}


def normalize(payload: dict, event: str) -> dict:
    value = dict(payload)
    value.setdefault("session_id", value.get("conversation_id") or value.get("parent_conversation_id", ""))
    roots = value.get("workspace_roots") or []
    if roots:
        value.setdefault("cwd", roots[0])
    if "tool_output" in value:
        value.setdefault("tool_response", value["tool_output"])
    if "error_message" in value:
        value.setdefault("tool_response", value["error_message"])
    if "text" in value:
        value.setdefault("last_assistant_message", value["text"])
    if "summary" in value:
        value.setdefault("last_assistant_message", value["summary"])
    if "subagent_id" in value:
        value.setdefault("agent_id", value["subagent_id"])
    if "subagent_type" in value:
        value.setdefault("agent_type", value["subagent_type"])
    return {"action": EVENTS[event], "payload": value}


def _record_failure(store, payload):
    return record_tool(store, payload, failed=True)


def _record_response(store, payload):
    hook_runner.default_record_stop(store, payload)


def _record_sidekick_start(store, payload):
    record_sidekick_start(store, payload)
    return {"permission": "allow"}


def _record_sidekick_stop(store, payload):
    record_sidekick_stop(store, payload)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in EVENTS:
        return 2
    event = sys.argv[1]
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        raw = {}
    normalized = normalize(raw if isinstance(raw, dict) else {}, event)
    action = normalized["action"]
    arguments = {
        "session-end": ["flush", "--reason", "session-end"],
        "pre-compact": ["flush", "--reason", "pre-compact"],
    }.get(action, [action])
    sys.argv = [sys.argv[0], *arguments]
    sys.stdin = io.StringIO(json.dumps(normalized["payload"]))

    configure_harness("cursor", data_dir_name="cursor-plugin", source_tag="cursor_plugin")
    telemetry.init(harness="cursor", source_tag="CURSOR_PLUGIN")
    with contextlib.redirect_stdout(io.StringIO()):
        result = hook_runner.run(
            extra_actions={
                "post-tool-failure": _record_failure,
                "assistant-stop": _record_response,
                "sidekick-start": _record_sidekick_start,
                "sidekick-stop": _record_sidekick_stop,
            },
            automatic_flush_reasons={"session-end", "pre-compact"},
        )
    if event == "sessionStart":
        environment = {
            key: value
            for key in (
                "PLUGIN_OPTION_API_KEY",
                "PLUGIN_OPTION_USER_ID",
                "PLUGIN_OPTION_TOP_K",
                "PLUGIN_OPTION_MAX_CONTEXT_CHARS",
                "PLUGIN_OPTION_SEARCH_SCOPE",
            )
            if (value := os.environ.get(key))
        }
        if environment:
            print(json.dumps({"env": environment}))
    elif event == "subagentStart":
        print(json.dumps({"permission": "allow"}))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
