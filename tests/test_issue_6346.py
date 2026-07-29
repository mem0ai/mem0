"""Regression test for fresh Agent Mode bootstrap MCP readiness (issue #6346)."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from mem0 import MemoryClient


def test_issue_6346(monkeypatch, tmp_path, capsys) -> None:
    """A fresh Codex bootstrap must report JSON that matches its MCP auth state."""
    # Keep this root-level regression test connected to the shipped SDK while
    # exercising the CLI implementation that creates Agent Mode credentials.
    assert MemoryClient.__module__ == "mem0.client.main"

    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(repo_root / "cli" / "python" / "src"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("MEM0_API_KEY", raising=False)

    from mem0_cli import config as cli_config
    from mem0_cli import plugin_sync
    from mem0_cli import state
    from mem0_cli.commands import agent_mode_cmd, init_cmd
    from mem0_cli import telemetry

    config_dir = tmp_path / ".mem0"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(cli_config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cli_config, "CONFIG_FILE", config_file)
    monkeypatch.setattr(init_cmd, "CONFIG_FILE", config_file)
    monkeypatch.setattr(plugin_sync, "_CLAUDE_SETTINGS", tmp_path / ".claude" / "settings.json")
    monkeypatch.setattr(
        plugin_sync,
        "_SHELL_RCS",
        [tmp_path / ".zshrc", tmp_path / ".bashrc", tmp_path / ".bash_profile"],
    )
    monkeypatch.setattr(telemetry, "capture_event", lambda *args, **kwargs: None)

    class _Response:
        status_code = 200

        def json(self):
            return {
                "api_key": "m0-test-agent-key",
                "default_user_id": "user_test_agent",
                "claim_command": "mem0 init --email owner@example.com",
            }

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return _Response()

    monkeypatch.setattr(agent_mode_cmd.httpx, "Client", _Client)

    previous_agent_mode = state.is_agent_mode()
    state.set_agent_mode(True)  # Equivalent to the command's trailing --json flag.
    try:
        init_cmd.run_init(agent=True, agent_caller="codex")
    finally:
        state.set_agent_mode(previous_agent_mode)

    saved_config = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_config["platform"]["api_key"] == "m0-test-agent-key"
    assert saved_config["defaults"]["user_id"] == "user_test_agent"
    assert stat.S_IMODE(config_file.stat().st_mode) == 0o600

    codex_manifest = json.loads(
        (repo_root / "integrations" / "mem0-plugin" / ".codex-mcp.json").read_text(encoding="utf-8")
    )
    auth_env_var = codex_manifest["mcpServers"]["mem0"]["bearer_token_env_var"]
    mcp_is_authenticated = os.environ.get(auth_env_var) == "m0-test-agent-key"

    # A fresh home has no existing shell, Claude, or Codex credential entry;
    # the manifest's first authentication source is therefore decisive.
    assert not (tmp_path / ".zshrc").exists()
    assert not (tmp_path / ".bashrc").exists()

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert payload["command"] == "init"
    assert payload["data"]["api_key_saved"] is True
    assert payload["data"]["default_user_id"] == "user_test_agent"
    assert payload["data"]["mcp_ready"] is mcp_is_authenticated
    assert isinstance(payload["data"]["next_step"], str)
    assert payload["data"]["next_step"]
