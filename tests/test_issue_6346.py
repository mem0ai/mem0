"""Regression test for Agent Mode's fresh-plugin readiness report."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


def test_issue_6346(monkeypatch, tmp_path):
    """A fresh Codex bootstrap must report its actual MCP authentication state."""
    cli_source = Path(__file__).parents[1] / "cli" / "python" / "src"
    monkeypatch.syspath_prepend(str(cli_source))
    import mem0_cli

    assert mem0_cli.__package__ == "mem0_cli"

    class AgentModeHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == "/api/v1/auth/agent_mode/"
            content_length = int(self.headers["Content-Length"])
            assert json.loads(self.rfile.read(content_length)) == {"agent_caller": "codex"}

            response = json.dumps(
                {
                    "api_key": "m0-synthetic-agent-key",
                    "default_user_id": "user_issue_6346",
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), AgentModeHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    env = {key: value for key, value in os.environ.items() if not key.startswith("MEM0_")}
    env.update(
        {
            "HOME": str(tmp_path),
            "MEM0_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "PYTHONIOENCODING": "utf-8",
            "FORCE_COLOR": "0",
            "PYTHONPATH": os.pathsep.join(filter(None, [str(cli_source), os.environ.get("PYTHONPATH")])),
        }
    )

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mem0_cli",
                "init",
                "--agent",
                "--agent-caller",
                "codex",
                "--json",
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            timeout=15,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join()

    assert result.returncode == 0, result.stderr

    config_file = tmp_path / ".mem0" / "config.json"
    config = json.loads(config_file.read_text(encoding="utf-8"))
    assert config_file.stat().st_mode & 0o777 == 0o600
    assert config["platform"]["api_key"] == "m0-synthetic-agent-key"
    assert config["defaults"]["user_id"] == "user_issue_6346"

    codex_manifest = json.loads(
        (Path(__file__).parents[1] / "integrations" / "mem0-plugin" / ".codex-mcp.json").read_text(
            encoding="utf-8"
        )
    )
    assert codex_manifest["mcpServers"]["mem0"]["bearer_token_env_var"] == "MEM0_API_KEY"
    assert "MEM0_API_KEY" not in env
    assert not (tmp_path / ".zshrc").exists()
    assert not (tmp_path / ".bashrc").exists()
    assert not (tmp_path / ".claude" / "settings.json").exists()

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Expected a JSON success envelope, got: {result.stdout!r}")

    assert envelope["status"] == "success"
    assert envelope["command"] == "init"
    assert envelope["data"]["api_key_saved"] is True
    assert envelope["data"]["default_user_id"] == "user_issue_6346"
    assert envelope["data"]["mcp_ready"] is False
    assert envelope["data"]["next_step"]
