"""Launch each host's real hooks and MCP server the way the host does, and check the search is authenticated."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template

import pytest

INTEGRATIONS = Path(__file__).resolve().parents[2]
KEY = "m0-plugin-setting-key"
CODEX_INHERITED_ENV = ("HOME", "PATH", "LANG", "TMPDIR")


class _Mem0Api(BaseHTTPRequestHandler):
    authorizations: list[str]

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.authorizations.append(self.headers.get("Authorization", ""))
        body = b'{"results": []}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def mem0_api():
    handler = type("Handler", (_Mem0Api,), {"authorizations": []})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", handler.authorizations
    server.shutdown()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _expand(value: str, variables: dict[str, str]) -> str:
    return Template(value).safe_substitute(variables)


def _run_hook(command: str, cwd: Path, env: dict[str, str], payload: dict) -> None:
    result = subprocess.run(
        ["sh", "-c", command], cwd=cwd, env=env, input=json.dumps(payload), text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr


def _search(argv: list[str], cwd: Path, env: dict[str, str]) -> dict:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "search_memories", "arguments": {"query": "earlier fixes"}},
        },
    ]
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        input="\n".join(json.dumps(request) for request in requests) + "\n",
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.splitlines()[-1])


def _claude_code(host_env: dict[str, str], tmp_path: Path, repo: Path, setting: bool) -> tuple:
    root = INTEGRATIONS / "claude-code-plugin"
    plugin_env = {"CLAUDE_PLUGIN_ROOT": str(root), "CLAUDE_PLUGIN_DATA": str(tmp_path / "claude-data")}
    hook_env = {**host_env, **plugin_env, **({"CLAUDE_PLUGIN_OPTION_API_KEY": KEY} if setting else {})}
    command = _json(root / "hooks" / "hooks.json")["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    _run_hook(command, repo, hook_env, {"session_id": "s1", "cwd": str(repo)})

    server = _json(root / ".mcp.json")["mcpServers"]["mem0"]
    env = {**host_env, **{name: _expand(value, plugin_env) for name, value in server["env"].items()}}
    return [sys.executable, *(_expand(argument, plugin_env) for argument in server["args"])], repo, env


def _cursor(host_env: dict[str, str], tmp_path: Path, repo: Path, setting: bool) -> tuple:
    root = INTEGRATIONS / "cursor-plugin"
    command = _json(root / "hooks" / "hooks.json")["hooks"]["sessionStart"][0]["command"]
    if setting:
        command = command.replace("${api_key}", KEY)
    hook_env = {**host_env, "CURSOR_PLUGIN_ROOT": str(root)}
    _run_hook(command, repo, hook_env, {"conversation_id": "c1", "workspace_roots": [str(repo)]})

    server = _json(root / "mcp.json")["mcpServers"]["mem0"]
    args = [_expand(argument, {"CURSOR_PLUGIN_ROOT": str(root)}) for argument in server["args"]]
    return [sys.executable, *args], repo, {**host_env, **server["env"]}


def _codex(host_env: dict[str, str], tmp_path: Path, repo: Path, setting: bool) -> tuple:
    root = INTEGRATIONS / "codex-plugin"
    codex_env = {**host_env, **({"MEM0_API_KEY": KEY} if setting else {})}
    data = str(tmp_path / "codex-data")
    hook_env = {**codex_env, "PLUGIN_ROOT": str(root), "PLUGIN_DATA": data, "CLAUDE_PLUGIN_DATA": data}
    command = _json(root / "hooks" / "hooks.json")["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    _run_hook(command, repo, hook_env, {"session_id": "s1", "cwd": str(repo)})

    server = _json(root / ".mcp.json")["mcpServers"]["mem0"]
    forwarded = [*CODEX_INHERITED_ENV, *server["env_vars"]]
    env = {name: codex_env[name] for name in forwarded if name in codex_env}
    return [sys.executable, *server["args"]], root / server["cwd"], env


HOSTS = {"claude-code": _claude_code, "cursor": _cursor, "codex": _codex}


def _mem0_init(home: Path, key: str) -> None:
    (home / ".mem0").mkdir(parents=True, exist_ok=True)
    (home / ".mem0" / "config.json").write_text(json.dumps({"platform": {"api_key": key}}), encoding="utf-8")


def _host_env(home: Path, api_url: str) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "MEM0_API_URL": api_url,
        "MEM0_TELEMETRY": "false",
        "MEM0_CODE_USER_ID": "test-user",
    }


@pytest.mark.parametrize("key_source", ["plugin setting", "mem0 init"])
@pytest.mark.parametrize("host", sorted(HOSTS))
def test_mcp_server_searches_with_the_key_the_user_configured(host, key_source, tmp_path, mem0_api):
    """The key reaches the MCP server however the host delivers it: plugin setting, env, or `mem0 init`."""
    api_url, authorizations = mem0_api
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    if key_source == "mem0 init":
        _mem0_init(home, KEY)

    argv, cwd, env = HOSTS[host](_host_env(home, api_url), tmp_path, repo, key_source == "plugin setting")
    response = _search(argv, cwd, env)

    assert not response["result"].get("isError"), response
    assert authorizations == [f"Token {KEY}"]


@pytest.mark.parametrize("host", sorted(HOSTS))
def test_a_removed_plugin_setting_gives_way_to_a_later_mem0_init(host, tmp_path, mem0_api):
    """The key saved from a plugin setting is dropped once the setting is gone, so a newer `mem0 init` key wins."""
    api_url, authorizations = mem0_api
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    host_env = _host_env(home, api_url)
    HOSTS[host](host_env, tmp_path, repo, True)
    _mem0_init(home, "m0-mem0-init-key")

    argv, cwd, env = HOSTS[host](host_env, tmp_path, repo, False)
    response = _search(argv, cwd, env)

    assert not response["result"].get("isError"), response
    assert authorizations == ["Token m0-mem0-init-key"]
