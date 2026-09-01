"""Configure harness identity and disable live telemetry for the test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["MEM0_TELEMETRY"] = "false"

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
_local_core = PLUGIN_ROOT / "core"
_shared_core = PLUGIN_ROOT.parent / "plugin-core"
_core = _local_core if _local_core.exists() else _shared_core
sys.path.insert(0, str(_core))

from memory_core import configure_harness  # noqa: E402
import telemetry  # noqa: E402

configure_harness("claude-code", data_dir_name="claude-code-plugin", source_tag="claude_code_plugin")
telemetry.init(harness="claude-code", source_tag="CLAUDE_CODE_PLUGIN")
