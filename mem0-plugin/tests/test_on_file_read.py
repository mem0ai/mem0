"""Tests for on_file_read.sh hook — skip rules and dedup logic."""

from __future__ import annotations

import json
import os
import subprocess

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "on_file_read.sh")


def _run_hook(file_path: str, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "MEM0_API_KEY": "", "USER": "testuser"}
    if env_overrides:
        env.update(env_overrides)

    payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": file_path}})
    return subprocess.run(
        ["bash", SCRIPT],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
    )


def test_skip_png():
    result = _run_hook("/project/logo.png")
    assert result.returncode == 0
    assert result.stdout == ""


def test_skip_lockfile():
    result = _run_hook("/project/package-lock.json")
    assert result.returncode == 0
    assert result.stdout == ""


def test_skip_min_js():
    result = _run_hook("/project/dist/bundle.min.js")
    assert result.returncode == 0
    assert result.stdout == ""


def test_skip_node_modules():
    result = _run_hook("/project/node_modules/lodash/index.js")
    assert result.returncode == 0
    assert result.stdout == ""


def test_skip_git_dir():
    result = _run_hook("/project/.git/config")
    assert result.returncode == 0
    assert result.stdout == ""


def test_skip_pycache():
    result = _run_hook("/project/__pycache__/module.cpython-311.pyc")
    assert result.returncode == 0
    assert result.stdout == ""


def test_skip_no_api_key():
    """Code file but no API key — should exit cleanly with no output."""
    result = _run_hook("/project/src/app.py", {"MEM0_API_KEY": ""})
    assert result.returncode == 0
    assert result.stdout == ""


def test_skip_empty_file_path():
    """Empty file_path — should exit cleanly."""
    result = _run_hook("")
    assert result.returncode == 0
    assert result.stdout == ""


def test_dedup_repeated_reads(tmp_path):
    """Same file read twice — second should be skipped (via dedup file)."""
    dedup_file = str(tmp_path / "mem0_recent_reads_testuser")
    env = {"MEM0_API_KEY": "fake-key", "USER": "testuser"}

    # Write the file path into the dedup tracking file
    with open(dedup_file, "w") as f:
        f.write("/project/src/app.py\n")

    # Patch RECENT_FILE by providing the USER env and ensuring /tmp has the file
    # Since the script uses /tmp/mem0_recent_reads_${USER}, we create it there
    tmp_dedup = "/tmp/mem0_recent_reads_testuser"
    try:
        with open(tmp_dedup, "w") as f:
            f.write("/project/src/app.py\n")

        result = _run_hook("/project/src/app.py", env)
        assert result.returncode == 0
        assert result.stdout == ""
    finally:
        if os.path.exists(tmp_dedup):
            os.remove(tmp_dedup)
