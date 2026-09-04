from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

HOST = Path(__file__).resolve().parents[1]
CORE_ROOT = HOST.parent / "agent-plugin-core"
sys.path.insert(0, str(CORE_ROOT))

from build.build import build  # noqa: E402


def test_codex_hooks_use_native_events_and_plugin_paths() -> None:
    hooks = json.loads((HOST / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]

    assert set(hooks) == {
        "SessionStart",
        "UserPromptSubmit",
        "PostToolUse",
        "SubagentStart",
        "SubagentStop",
        "Stop",
        "PreCompact",
        "SessionEnd",
    }
    commands = [hook["command"] for groups in hooks.values() for group in groups for hook in group["hooks"]]
    assert "matcher" not in hooks["SubagentStart"][0]
    assert "matcher" not in hooks["SubagentStop"][0]
    assert all("${PLUGIN_ROOT}/hooks/adapter.py" in command for command in commands)
    assert any("flush --reason pre-compact" in command for command in commands)
    assert any("flush --reason session-end" in command for command in commands)
    assert all(hook.get("timeout", 0) <= 3 for groups in hooks.values() for group in groups for hook in group["hooks"])


def test_codex_sidekick_records_lifecycle(tmp_path: Path) -> None:
    adapter = HOST / "hooks" / "adapter.py"
    payload = {
        "session_id": "session-1",
        "cwd": str(tmp_path),
        "agent_id": "agent-1",
        "agent_type": "default",
    }

    for action, extra in (
        ("sidekick-start", {}),
        ("sidekick-stop", {"last_assistant_message": "SIDEKICK_OK"}),
    ):
        result = subprocess.run(
            [sys.executable, str(adapter), action, "--plugin-data-dir", str(tmp_path / "data")],
            input=json.dumps({**payload, **extra}),
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    with sqlite3.connect(tmp_path / "data" / "evidence.sqlite3") as connection:
        row = connection.execute(
            "SELECT agent_id, stopped_at, final_message FROM sidekick_runs"
        ).fetchone()

    assert row is not None
    assert row[0] == "agent-1"
    assert row[1]
    assert row[2] == "SIDEKICK_OK"


def test_codex_mcp_uses_host_relative_paths() -> None:
    manifest = json.loads((HOST / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["mcpServers"] == "./.mcp.json"

    server = json.loads((HOST / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["mem0"]
    assert server["command"] == "python3"
    assert server["args"] == ["./core/mcp_server.py"]
    assert server["cwd"] == "."
    assert set(server["env_vars"]) >= {"MEM0_API_KEY", "MEM0_CODE_USER_ID"}
    assert "PLUGIN_ROOT" not in json.dumps(server)


def test_native_codex_bundle_is_self_contained(tmp_path: Path) -> None:
    root = build("codex", "native", tmp_path / "codex")

    manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["hooks"] == "./hooks/hooks.json"
    assert manifest["skills"] == "./skills/"
    assert (root / "hooks" / "adapter.py").is_file()
    assert (root / "core" / "mcp_server.py").is_file()
    assert (root / ".mcp.json").is_file()
    assert not (root / "agents").exists()
    assert not any(path.is_symlink() for path in root.rglob("*"))
