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
from memory_core import configure_harness, record_sidekick_start, record_sidekick_stop  # noqa: E402

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


if __name__ == "__main__":
    hook_runner.entry_point(
        extra_actions={"sidekick-start": _sidekick_start, "sidekick-stop": _sidekick_stop},
        automatic_flush_reasons={"session-end", "pre-compact"},
    )
