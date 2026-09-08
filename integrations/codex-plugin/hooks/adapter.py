#!/usr/bin/env python3
"""Run Codex hooks through the shared Mem0 runtime."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
BUNDLED_CORE = HERE.parent.parent / "core"
CORE = BUNDLED_CORE if BUNDLED_CORE.is_dir() else HERE.parents[2] / "core" / "python"
sys.path.insert(0, str(CORE))

import hook_runner  # noqa: E402
import telemetry  # noqa: E402
from memory_core import (  # noqa: E402
    configure_harness,
    record_sidekick_start,
    record_sidekick_stop,
    record_tool,
)

configure_harness("codex", data_dir_name="codex-plugin", source_tag="codex_plugin")
telemetry.init(harness="codex", source_tag="CODEX_PLUGIN")


def _sidekick_start(store, hook_input):
    context = record_sidekick_start(store, hook_input)
    if context:
        return {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": context,
            }
        }


def _sidekick_stop(store, hook_input):
    record_sidekick_stop(store, hook_input)


def _post_tool(store, payload):
    response = payload.get("tool_response")
    failed = None
    if isinstance(response, dict):
        exit_code = response.get("exit_code")
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            failed = exit_code != 0
        elif isinstance(response.get("isError"), bool):
            failed = response["isError"]
        elif isinstance(response.get("success"), bool):
            failed = not response["success"]
    if failed:
        payload = {**payload, "error": response}
    record_tool(store, payload, failed=failed)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "post-tool":
        sys.argv[1] = "codex-post-tool"
    hook_runner.entry_point(
        extra_actions={"sidekick-start": _sidekick_start, "sidekick-stop": _sidekick_stop, "codex-post-tool": _post_tool},
        automatic_flush_reasons={"session-end", "pre-compact"},
    )
