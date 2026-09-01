#!/usr/bin/env python3
"""Harmless hooks for Mem0."""

from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve()
_local_core = _here.parents[2] / "core"
_shared_core = _here.parents[3] / "plugin-core"
_core_dir = _local_core if _local_core.exists() else _shared_core
sys.path.insert(0, str(_core_dir))

import telemetry  # noqa: E402
from memory_core import configure_harness  # noqa: E402
import hook_runner  # noqa: E402

configure_harness("harmless", data_dir_name="harmless-plugin", source_tag="harmless_plugin")
telemetry.init(harness="harmless", source_tag="HARMLESS_PLUGIN")

if __name__ == "__main__":
    hook_runner.entry_point()
