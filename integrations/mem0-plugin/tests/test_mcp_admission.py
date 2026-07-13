"""MCP manifest and PreToolUse admission contracts."""

from __future__ import annotations

import json
import os
import subprocess

import pytest


PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_ROOT, "scripts", "enforce_metadata_defaults.sh")


def _manifest_matchers(path):
    with open(path) as handle:
        data = json.load(handle)
    hooks = data["hooks"]
    entries = hooks.get("PreToolUse", hooks.get("preToolUse", []))
    return [entry.get("matcher", "") for entry in entries]


@pytest.mark.parametrize(
    "relative",
    ["hooks/hooks.json", "hooks/codex-hooks.json", "hooks/cursor-hooks.json", "hooks.json"],
)
def test_every_manifest_uses_broad_mem0_matcher(relative):
    matchers = _manifest_matchers(os.path.join(PLUGIN_ROOT, relative))
    assert "mcp__mem0__.*|mcp__plugin_mem0_mem0__.*" in matchers


def _run_hook(tmp_path, tool_name, extra_env=None):
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "MEM0_STATE_DIR": str(tmp_path / "state"),
            "MEM0_PROJECT_ID": "project",
            "MEM0_USER_ID": "user",
            "MEM0_BUDGET_SESSION_REQUESTS": "20",
            "MEM0_BUDGET_DAILY_REQUESTS": "20",
            "MEM0_BUDGET_SESSION_AUTO_REQUESTS": "20",
            "MEM0_BUDGET_DAILY_AUTO_REQUESTS": "20",
            "MEM0_BUDGET_SESSION_WEIGHT": "100",
            "MEM0_BUDGET_DAILY_WEIGHT": "100",
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [SCRIPT],
        input=json.dumps({"tool_name": tool_name, "tool_input": {}}),
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "operation",
    [
        "add_memory",
        "search_memories",
        "get_memories",
        "get_memory",
        "update_memory",
        "delete_memory",
        "delete_all_memories",
        "delete_entities",
        "list_entities",
    ],
)
def test_all_advertised_mcp_operations_are_classified_and_admitted(tmp_path, operation):
    result = _run_hook(tmp_path, f"mcp__mem0__{operation}")
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_unknown_mem0_operation_is_typed_deny_without_charge(tmp_path):
    result = _run_hook(tmp_path, "mcp__mem0__future_operation")
    assert result.returncode == 2
    assert "remote-unknown-operation" in result.stderr
    assert not (tmp_path / "state" / "admission.sqlite3").exists()


@pytest.mark.parametrize(
    "operation",
    [
        "add_memory",
        "search_memories",
        "get_memories",
        "get_memory",
        "update_memory",
        "delete_memory",
        "delete_all_memories",
        "delete_entities",
        "list_entities",
    ],
)
def test_budget_denial_returns_pretooluse_deny_for_every_operation(tmp_path, operation):
    result = _run_hook(
        tmp_path,
        f"mcp__mem0__{operation}",
        {"MEM0_BUDGET_SESSION_REQUESTS": "0"},
    )
    assert result.returncode == 2
    assert "remote-session-budget-exhausted" in result.stderr
