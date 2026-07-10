"""Regression test for mem0 plugin auto_search hook gating.

Verifies that hook-driven searches in integrations/mem0-plugin honor
~/.mem0/settings.json auto_search=false, instead of continuing to call the
file-context and bash error search paths and silently consuming API quota.
"""

import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

client_main = types.ModuleType("mem0.client.main")
client_main.AsyncMemoryClient = type("AsyncMemoryClient", (), {})
client_main.MemoryClient = type("MemoryClient", (), {})
memory_main = types.ModuleType("mem0.memory.main")
memory_main.AsyncMemory = type("AsyncMemory", (), {})
memory_main.Memory = type("Memory", (), {})
sys.modules.setdefault("mem0.client.main", client_main)
sys.modules.setdefault("mem0.memory.main", memory_main)

with patch("importlib.metadata.version", return_value="0.0.0"):
    import mem0


def test_issue_6065(tmp_path):
    assert mem0 is not None

    if not shutil.which("bash"):
        pytest.skip("bash not installed")
    if not shutil.which("jq"):
        pytest.skip("jq not installed")

    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "integrations" / "mem0-plugin" / "scripts"

    calls_file = tmp_path / "python_calls.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real_python = sys.executable
    python_shim = bin_dir / "python3"
    python_shim.write_text(
        f"""#!/usr/bin/env bash
set -e
if [[ "${{1:-}}" == *"file_context.py" ]]; then
  echo "file_context" >> "{calls_file}"
  exit 0
fi
if [[ "${{1:-}}" == "-c" && "${{2:-}}" == *"search_memories"* ]]; then
  echo "bash_search" >> "{calls_file}"
  exit 0
fi
if [[ "${{1:-}}" == *"telemetry.py" ]]; then
  exit 0
fi
exec "{real_python}" "$@"
""",
        encoding="utf-8",
    )
    python_shim.chmod(0o755)

    home_dir = tmp_path / "home"
    settings_dir = home_dir / ".mem0"
    settings_dir.mkdir(parents=True)
    (settings_dir / "settings.json").write_text(json.dumps({"auto_search": False}), encoding="utf-8")

    env = {
        **os.environ,
        "HOME": str(home_dir),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "CLAUDE_PLUGIN_OPTION_API_KEY": "fake-key",
        "USER": "issue-6065-user",
    }
    env.pop("MEM0_API_KEY", None)
    env.pop("MEM0_AUTO_SEARCH", None)

    file_read_input = {
        "tool_name": "Read",
        "tool_input": {"file_path": str(repo_root / "README.md")},
        "cwd": str(repo_root),
    }
    subprocess.run(
        ["bash", str(scripts_dir / "on_file_read.sh")],
        input=json.dumps(file_read_input),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    bash_output_input = {
        "tool_name": "Bash",
        "tool_input": {"command": "cat fixture.log"},
        "tool_response": "Error: first fixture line\n" + ("x" * 60) + "\nError: second fixture line\n",
    }
    subprocess.run(
        ["bash", str(scripts_dir / "on_bash_output.sh")],
        input=json.dumps(bash_output_input),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    calls = calls_file.read_text(encoding="utf-8").splitlines() if calls_file.exists() else []
    assert calls == []
