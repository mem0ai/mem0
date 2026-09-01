#!/usr/bin/env python3
"""Spec plugin hook entry point for Mem0."""
from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve()
_local_core = _here.parents[1] / "core"
_shared_core = _here.parents[2] / "plugin-core"
sys.path.insert(0, str(_local_core if _local_core.exists() else _shared_core))

import hook_runner  # noqa: E402

if __name__ == "__main__":
    hook_runner.entry_point()
