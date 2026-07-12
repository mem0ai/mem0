"""Regression: Cursor on_file_read honors MEM0_AUTO_SEARCH (#6252)."""

from __future__ import annotations

import json
import os
import subprocess
from unittest.mock import patch

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
HOOK = os.path.join(SCRIPTS_DIR, "on_file_read_cursor.sh")


def _run(env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "MEM0_API_KEY": "test-key",
        "MEM0_AUTO_SEARCH": "false",
        "PATH": os.environ.get("PATH", ""),
    }
    if env_extra:
        env.update(env_extra)
    payload = json.dumps({"tool_input": {"file_path": "/tmp/example.py"}, "cwd": "/tmp"})
    return subprocess.run(
        ["bash", HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def test_auto_search_false_exits_without_timeline(tmp_path, monkeypatch):
    """When auto_search is off, hook must not invoke file_context.py work.

    We assert empty stdout (no additionalContext JSON) and success exit.
    """
    # Point PYTHON so if file_context were called it would be findable; we still
    # expect no context emission when auto_search is false.
    result = _run()
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_auto_search_true_may_emit(tmp_path, monkeypatch):
    """Control: with auto_search true the hook still exits 0 (file_context may no-op)."""
    result = _run({"MEM0_AUTO_SEARCH": "true"})
    assert result.returncode == 0
