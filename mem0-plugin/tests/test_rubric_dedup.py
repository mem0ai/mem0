"""Tests for rubric deduplication in on_user_prompt.sh."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


@pytest.fixture(autouse=True)
def _clean_rubric_flag(tmp_path, monkeypatch):
    """Use a temp dir for the rubric flag file."""
    monkeypatch.setenv("MEM0_RUBRIC_DIR", str(tmp_path))
    yield


def _run_hook(prompt: str, env_overrides: dict | None = None, session_id: str = "test-sess-001") -> str:
    """Run on_user_prompt.sh with a simulated prompt and return stdout."""
    env = {
        **os.environ,
        "USER": "testuser",
        "MEM0_API_KEY": "test-key-123",
        "MEM0_RESOLVED_USER_ID": "testuser",
        "MEM0_PROJECT_ID": "test-project",
        "MEM0_BRANCH": "main",
    }
    if env_overrides:
        env.update(env_overrides)

    input_json = json.dumps({"prompt": prompt, "session_id": session_id})
    result = subprocess.run(
        ["bash", os.path.join(SCRIPTS_DIR, "on_user_prompt.sh")],
        input=input_json,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return result.stdout


def test_first_prompt_gets_full_rubric():
    """First substantial prompt of session gets full memory check rubric."""
    output = _run_hook("How should we refactor the auth module?")
    assert "Search mem0" in output
    assert "Search tips" in output
    assert "metadata.type" in output


def test_second_prompt_gets_no_rubric():
    """Second prompt of session emits nothing — rubric and tips only on first prompt."""
    _run_hook("How should we refactor the auth module?")
    output = _run_hook("What about the database layer?")
    assert output.strip() == ""
