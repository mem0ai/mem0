#!/usr/bin/env python3
"""Translate GitHub Copilot CLI hooks into the shared Mem0 runtime."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
BUNDLED_CORE = HERE.parent.parent / "core"
CORE = BUNDLED_CORE if BUNDLED_CORE.is_dir() else HERE.parents[2] / "agent-plugin-core" / "python"
sys.path.insert(0, str(CORE))

import hook_runner  # noqa: E402
import telemetry  # noqa: E402
from memory_core import (  # noqa: E402
    configure_harness,
    record_tool,
)

EVENTS = {
    "sessionStart": ["session-start"],
    "SessionStart": ["session-start"],
    "userPromptSubmitted": ["user-prompt"],
    "UserPromptSubmit": ["user-prompt"],
    "UserPromptSubmitted": ["user-prompt"],
    "postToolUse": ["copilot-post-tool"],
    "PostToolUse": ["copilot-post-tool"],
    "agentStop": ["stop"],
    "AgentStop": ["stop"],
    "Stop": ["stop"],
    "sessionEnd": ["flush", "--reason", "session-end"],
    "SessionEnd": ["flush", "--reason", "session-end"],
}


def normalize(payload: dict) -> dict:
    value = dict(payload)
    if "sessionId" in value:
        value.setdefault("session_id", value["sessionId"])
    if "toolName" in value:
        value.setdefault("tool_name", value["toolName"])
    if "toolInput" in value:
        value.setdefault("tool_input", value["toolInput"])
    if value.get("error"):
        value.setdefault("tool_response", value["error"])
    elif "output" in value:
        value.setdefault("tool_response", value["output"])
    if "response" in value:
        value.setdefault("last_assistant_message", value["response"])
    return value


def _post_tool(store, payload):
    response = payload.get("tool_response")
    failed = None
    if payload.get("error"):
        failed = True
    elif isinstance(response, dict):
        exit_code = response.get("exitCode") or response.get("exit_code")
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            failed = exit_code != 0
        elif isinstance(response.get("isError"), bool):
            failed = response["isError"]
        elif isinstance(response.get("success"), bool):
            failed = not response["success"]
    elif "exitCode" in payload or "exit_code" in payload:
        exit_code = payload.get("exitCode") or payload.get("exit_code")
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            failed = exit_code != 0

    if failed:
        payload = {**payload, "error": payload.get("error") or response or "Tool execution failed"}
    record_tool(store, payload, failed=failed)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in EVENTS:
        return 2
    event = sys.argv[1]
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        raw = {}
    payload = normalize(raw if isinstance(raw, dict) else {})
    sys.argv = [sys.argv[0], *EVENTS[event]]
    sys.stdin = io.StringIO(json.dumps(payload))

    configure_harness("copilot", data_dir_name="copilot-plugin", source_tag="copilot_plugin")
    telemetry.init(harness="copilot", source_tag="COPILOT_PLUGIN")

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = hook_runner.run(
            record_stop_fn=hook_runner.default_record_stop,
            extra_actions={"copilot-post-tool": _post_tool},
            automatic_flush_reasons={"session-end"},
        )

    if event in {"userPromptSubmitted", "UserPromptSubmit", "UserPromptSubmitted"}:
        raw_output = output.getvalue().strip()
        if raw_output:
            try:
                parsed = json.loads(raw_output)
                context = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
                if context:
                    print(
                        json.dumps(
                            {
                                "additionalContext": context,
                                "hookSpecificOutput": {
                                    "hookEventName": "userPromptSubmitted",
                                    "additionalContext": context,
                                },
                            }
                        )
                    )
            except json.JSONDecodeError:
                pass

    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        hook_runner.log_failure(exc)
        raise SystemExit(0) from None
