#!/usr/bin/env python3
"""Claude Code hooks for Mem0."""

from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve()
_local_core = _here.parents[2] / "core"
_shared_core = _here.parents[3] / "plugin-core"
_core_dir = _local_core if _local_core.exists() else _shared_core
sys.path.insert(0, str(_core_dir))
sys.path.insert(0, str(_here.parent))

import telemetry  # noqa: E402
from memory_core import (  # noqa: E402
    configure_harness,
    record_sidekick_start,
    record_sidekick_stop,
    record_tool,
)
from transcript import record_stop  # noqa: E402
import hook_runner  # noqa: E402

configure_harness("claude-code", data_dir_name="claude-code-plugin", source_tag="claude_code_plugin")
telemetry.init(harness="claude-code", source_tag="CLAUDE_CODE_PLUGIN")


def _sidekick_start(store, hook_input):
    context = record_sidekick_start(store, hook_input)
    if context:
        return {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": context,
            },
        }


def _sidekick_stop(store, hook_input):
    record_sidekick_stop(store, hook_input)


if __name__ == "__main__":
    hook_runner.entry_point(
        record_stop_fn=record_stop,
        extra_actions={
            "post-tool-failure": lambda s, h: record_tool(s, h, failed=True),
            "sidekick-start": _sidekick_start,
            "sidekick-stop": _sidekick_stop,
        },
        data_dir_env="MEM0_CODE_DATA_DIR",
        automatic_flush_reasons={"session-end", "pre-compact"},
    )
