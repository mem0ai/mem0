#!/usr/bin/env python3
"""Translate Copilot CLI hooks into the shared Mem0 runtime."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
BUNDLED_CORE = HERE.parent.parent / "core"
CORE = BUNDLED_CORE if BUNDLED_CORE.is_dir() else HERE.parents[2] / "agent-plugin-core" / "python"
sys.path.insert(0, str(CORE))

import hook_runner  # noqa: E402
import telemetry  # noqa: E402
from memory_core import configure_harness, record_tool  # noqa: E402

EVENTS = {
    "sessionStart": ["session-start"],
    "userPromptSubmitted": ["user-prompt"],
    "postToolUse": ["post-tool"],
    "agentStop": ["stop"],
    "sessionEnd": ["flush", "--reason", "session-end"],
}


def normalize(payload: dict) -> dict:
    value = dict(payload)
    if "toolName" in value:
        value.setdefault("tool_name", value["toolName"])
    if "sessionId" in value:
        value.setdefault("session_id", value["sessionId"])
    if "output" in value:
        value.setdefault("tool_response", value["output"])
    if "error" in value:
        value.setdefault("tool_response", value["error"])
        value.setdefault("failed", True)
    return value


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in EVENTS:
        return 2
    event = sys.argv[1]
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        raw = {}

    sys.argv = [sys.argv[0], *EVENTS[event]]
    normalized = normalize(raw if isinstance(raw, dict) else {})
    sys.stdin = io.StringIO(json.dumps(normalized))

    configure_harness("copilot", data_dir_name="copilot-plugin", source_tag="copilot_plugin")
    telemetry.init(harness="copilot", source_tag="COPILOT_PLUGIN")

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = hook_runner.run(
            extra_actions={
                "post-tool": lambda store, payload: record_tool(store, payload, failed=payload.get("failed", False)),
            },
            automatic_flush_reasons={"session-end"},
        )

    if event == "userPromptSubmitted" and (raw_output := output.getvalue().strip()):
        try:
            parsed = json.loads(raw_output)
            context = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
            if context:
                print(context)
        except json.JSONDecodeError:
            pass
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        hook_runner.log_failure(exc)
        raise SystemExit(0) from None
