"""Clean-home bootstrap regression tests; mirrored by the Node CLI tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import httpx
import pytest

CLI_DIR = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((CLI_DIR.parents[1] / "integrations/mem0-plugin/.codex-mcp.json").read_text())
API_KEY = "m0-synthetic-bootstrap-key"
DEFAULT_USER_ID = "swift-otter-4821"
NOTICE = "Claim this account with mem0 init --email <your-email>."


@pytest.fixture
def bootstrap_server():
    response = {
        "api_key": API_KEY,
        "default_user_id": DEFAULT_USER_ID,
        "org_id": "test-org",
        "project_id": "test-project",
        "mem0_notice": NOTICE,
    }
    signup_requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path == "/api/v1/auth/agent_mode/":
                signup_requests.append(json.loads(body))
                status, data = 200, response
            elif self.path == "/mcp":
                status = 200 if self.headers.get("Authorization") == f"Bearer {API_KEY}" else 401
                data = {}
            else:
                status, data = 404, {}
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", response, signup_requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def clean_env(tmp_path, bootstrap_server):
    env = {key: value for key, value in os.environ.items() if not key.startswith("MEM0_")}
    env.pop("FORCE_COLOR", None)
    env.update(
        HOME=str(tmp_path),
        USERPROFILE=str(tmp_path),
        MEM0_BASE_URL=bootstrap_server[0],
        MEM0_TELEMETRY="false",
        NO_COLOR="1",
        PYTHONIOENCODING="utf-8",
    )
    return env


def run(args, env):
    return subprocess.run(
        [sys.executable, "-m", "mem0_cli", *args],
        cwd=CLI_DIR,
        env=env,
        capture_output=True,
        encoding="utf-8",
        timeout=15,
    )


def mcp_status(env, base_url):
    credential = env.get(MANIFEST["mcpServers"]["mem0"]["bearer_token_env_var"])
    headers = {"Authorization": f"Bearer {credential}"} if credential else {}
    return httpx.post(f"{base_url}/mcp", headers=headers).status_code


@pytest.mark.parametrize(
    "args",
    [
        ["init", "--agent", "--agent-caller", "codex", "--json"],
        ["--json", "init", "--agent", "--agent-caller", "codex"],
        ["--agent", "init", "--agent-caller", "codex"],
    ],
)
def test_bootstrap_json_and_mcp_handoff(args, clean_env, tmp_path, bootstrap_server):
    result = run(args, clean_env)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "\x1b[" not in result.stdout
    assert API_KEY not in result.stdout
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "success"
    assert envelope["command"] == "init"
    assert envelope["mem0_notice"] == NOTICE
    data = envelope["data"]
    assert data["api_key_saved"] is True
    assert data["api_key_source"] == "config"
    assert data["agent_mode"] is True
    assert data["default_user_id"] == DEFAULT_USER_ID
    assert data["mcp_ready"] is False
    assert data["claim_command"] == "mem0 init --email <your-email>"
    assert bootstrap_server[2] == [{"agent_caller": "codex"}]

    config_file = tmp_path / ".mem0/config.json"
    config = json.loads(config_file.read_text())
    assert config["platform"]["api_key"] == API_KEY
    assert config["platform"]["default_user_id"] == DEFAULT_USER_ID
    assert config["defaults"]["user_id"] == DEFAULT_USER_ID
    if sys.platform != "win32":
        assert config_file.stat().st_mode & 0o777 == 0o600
    for entry in (".bashrc", ".zshrc", ".bash_profile", ".claude/settings.json"):
        assert not (tmp_path / entry).exists()
    # The bundled manifest reads the host environment, not the CLI config.
    assert MANIFEST["mcpServers"]["mem0"]["bearer_token_env_var"] not in clean_env
    assert mcp_status(clean_env, bootstrap_server[0]) == 401

    next_step = data["next_step"]
    assert next_step["action"] == "set_environment_variable"
    assert next_step["name"] == MANIFEST["mcpServers"]["mem0"]["bearer_token_env_var"]
    assert Path(next_step["value_from"]["file"]) == config_file
    assert next_step["restart_required"] is True
    value = json.loads(Path(next_step["value_from"]["file"]).read_text())
    for part in next_step["value_from"]["key"].split("."):
        value = value[part]
    assert value == API_KEY
    assert mcp_status({**clean_env, next_step["name"]: value}, bootstrap_server[0]) == 200


def test_bootstrap_json_without_notice_or_caller(clean_env, bootstrap_server):
    response = bootstrap_server[1]
    response.pop("mem0_notice")
    response["claim_command"] = "mem0 init --email owner@example.com"
    result = run(["init", "--agent", "--json"], clean_env)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    envelope = json.loads(result.stdout)
    assert envelope["data"]["claim_command"] == response["claim_command"]
    assert "mem0_notice" not in envelope
    assert bootstrap_server[2] == [{}]


def test_bootstrap_human_output_explains_mcp_setup(clean_env):
    result = run(["init", "--agent", "--agent-caller", "codex"], clean_env)
    assert result.returncode == 0, result.stderr
    assert f"Agent Mode active. Default user_id: {DEFAULT_USER_ID}" in result.stdout
    assert "MEM0_API_KEY" in result.stdout
    assert "platform.api_key" in result.stdout
    assert "restart" in result.stdout
    assert NOTICE in result.stdout
    assert API_KEY not in result.stdout
