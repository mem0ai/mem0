"""Tests for the agent-driven provisioning endpoint.

The endpoint returns a self-contained manifest an agent executes to wire the
official plugin to THIS local server (zero cloud egress). These tests assert:

- GET /provision returns version, base_url, mcp_config, env, modes, recipe;
- the env enforces local-only + telemetry-off (no cloud binding);
- the 3 memory modes are present with exactly one default;
- per-host MCP config targets the right file/format;
- the /protocol alias returns behavioral text.

The provision router only depends on fastapi + os, so it is loaded directly
from its file (same approach as test_discovery.py).
"""

import importlib.util
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "provision.py"
_spec = importlib.util.spec_from_file_location("provision_under_test", _PATH)
_provision = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_provision)
provision_router = _provision.router


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(provision_router)
    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://memhost:8765") as ac:
        yield ac


class TestProvisionContract:
    @pytest.mark.asyncio
    async def test_returns_required_keys(self, client):
        resp = await client.get("/provision")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("version", "base_url", "mcp_config", "env", "modes", "recipe"):
            assert key in data, f"missing key: {key}"

    @pytest.mark.asyncio
    async def test_env_enforces_no_cloud_binding(self, client):
        env = (await client.get("/provision")).json()["env"]
        assert env["MEM0_LOCAL_ONLY"] == "1"
        assert env["MEM0_TELEMETRY"] == "false"
        assert env["OPENMEMORY_API_BASE"] == "http://memhost:8765"

    @pytest.mark.asyncio
    async def test_three_modes_with_single_default(self, client):
        modes = (await client.get("/provision")).json()["modes"]
        assert len(modes) == 3
        defaults = [m for m in modes if m.get("default")]
        assert len(defaults) == 1
        # The conservative default reads but does not auto-write.
        assert defaults[0]["settings"] == {"auto_search": True, "auto_save": False}

    @pytest.mark.asyncio
    async def test_mode_presets_cover_the_three_combinations(self, client):
        modes = (await client.get("/provision")).json()["modes"]
        combos = {(m["settings"]["auto_search"], m["settings"]["auto_save"]) for m in modes}
        assert combos == {(True, True), (True, False), (False, False)}


class TestPerHostMcpConfig:
    @pytest.mark.asyncio
    async def test_claude_code_writes_mcp_json(self, client):
        cfg = (await client.get("/provision?host=claude-code")).json()["mcp_config"]
        assert cfg["target_file"] == ".mcp.json"
        url = cfg["content"]["mcpServers"]["mem0"]["url"]
        assert url.startswith("http://memhost:8765/mcp/claude-code/http/")

    @pytest.mark.asyncio
    async def test_codex_writes_toml(self, client):
        cfg = (await client.get("/provision?host=codex")).json()["mcp_config"]
        assert cfg["format"] == "toml"
        assert cfg["target_file"] == "~/.codex/config.toml"
        assert "[mcp_servers.mem0]" in cfg["content"]

    @pytest.mark.asyncio
    async def test_cursor_writes_cursor_mcp_json(self, client):
        cfg = (await client.get("/provision?host=cursor")).json()["mcp_config"]
        assert cfg["target_file"] == ".cursor/mcp.json"

    @pytest.mark.asyncio
    async def test_unknown_host_falls_back_to_claude_code(self, client):
        data = (await client.get("/provision?host=bogus")).json()
        assert data["host"] == "claude-code"


class TestProtocolAlias:
    @pytest.mark.asyncio
    async def test_protocol_returns_text(self, client):
        data = (await client.get("/provision/protocol")).json()
        assert "protocol" in data
        assert "search_memories" in data["protocol"]
        assert "add_memory" in data["protocol"]
