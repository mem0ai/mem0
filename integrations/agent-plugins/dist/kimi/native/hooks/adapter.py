#!/usr/bin/env python3
"""Translate Kimi Code hooks into the shared Mem0 runtime."""

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
from memory_core import configure_harness, record_sidekick_start, record_sidekick_stop, record_tool  # noqa: E402

EVENTS = {
    "SessionStart": ["session-start"],
    "UserPromptSubmit": ["user-prompt"],
    "PostToolUse": ["post-tool"],
    "PostToolUseFailure": ["post-tool-failure"],
    "Stop": ["stop"],
    "PreCompact": ["flush", "--reason", "pre-compact"],
    "SessionEnd": ["flush", "--reason", "session-end"],
    "SubagentStart": ["sidekick-start"],
    "SubagentStop": ["sidekick-stop"],
}


def normalize(payload: dict) -> dict:
    value = dict(payload)
    if "tool_output" in value:
        value.setdefault("tool_response", value["tool_output"])
    if "error" in value:
        value.setdefault("tool_response", value["error"])
    if "response" in value:
        value.setdefault("last_assistant_message", value["response"])
    if "agent_name" in value:
        value.setdefault("agent_type", value["agent_name"])
        value.setdefault("agent_id", value["agent_name"])
    return value


def _sidekick_start(store, payload):
    context = record_sidekick_start(store, payload)
    return {"hookSpecificOutput": {"additionalContext": context}} if context else None


def _sidekick_stop(store, payload):
    record_sidekick_stop(store, payload)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in EVENTS:
        return 2
    event = sys.argv[1]
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        raw = {}
    sys.argv = [sys.argv[0], *EVENTS[event]]
    sys.stdin = io.StringIO(json.dumps(normalize(raw if isinstance(raw, dict) else {})))
    configure_harness("kimi", data_dir_name="kimi-plugin", source_tag="kimi_plugin")
    telemetry.init(harness="kimi", source_tag="KIMI_PLUGIN")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = hook_runner.run(
            extra_actions={
                "post-tool-failure": lambda store, payload: record_tool(store, payload, failed=True),
                "sidekick-start": _sidekick_start,
                "sidekick-stop": _sidekick_stop,
            },
            automatic_flush_reasons={"session-end", "pre-compact"},
        )
    if event in {"UserPromptSubmit", "SubagentStart"} and (raw_output := output.getvalue().strip()):
        parsed = json.loads(raw_output)
        context = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
        if context:
            print(context)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        hook_runner.log_failure(exc)
        raise SystemExit(0) from None
