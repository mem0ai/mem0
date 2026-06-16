"""Tests for the MCP auto-discovery endpoint (task_08 / ADR-005).

The endpoint returns a ready-to-use MCP connection config as JSON so agents can
self-configure. These tests assert:

- GET /discovery returns 200 with transport, base_url, route_template, fields;
- fields declare user_id=hostname and project as required;
- base_url reflects runtime (the request host, and an env override);
- the route_template is consistent with the real MCP route;
- the conventional /.well-known/mcp alias returns the same payload.

A minimal FastAPI app mounting only the discovery router is used (no DB / client
initialization needed).
"""

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Load the discovery router directly from its file. The module only depends on
# fastapi + os (no app imports), so this keeps the test a true unit test and
# avoids importing the routers package __init__ (which pulls in heavy siblings
# like fastapi_pagination / the OpenAI-initializing categorization module).
_DISCOVERY_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "discovery.py"
_spec = importlib.util.spec_from_file_location("discovery_under_test", _DISCOVERY_PATH)
_discovery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_discovery)
discovery_router = _discovery.router


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(discovery_router)
    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://memhost:8765") as ac:
        yield ac


class TestDiscoveryContract:
    @pytest.mark.asyncio
    async def test_returns_200_with_required_keys(self, client):
        resp = await client.get("/discovery")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("transport", "base_url", "route_template", "fields"):
            assert key in data, f"missing key: {key}"

    @pytest.mark.asyncio
    async def test_fields_declare_hostname_and_required_project(self, client):
        data = (await client.get("/discovery")).json()
        fields = data["fields"]
        assert fields["user_id"] == "hostname"
        assert fields["project"] == "obrigatório"
        assert "client_name" in fields

    @pytest.mark.asyncio
    async def test_route_template_matches_real_mcp_route(self, client):
        data = (await client.get("/discovery")).json()
        # Consistent with app.mcp_server's `/mcp/{client_name}/sse/{user_id}`.
        assert data["route_template"] == "/mcp/{client_name}/sse/{user_id}"
        assert data["transports"]["sse"] == "/mcp/{client_name}/sse/{user_id}"
        assert data["transports"]["http"] == "/mcp/{client_name}/http/{user_id}"
        assert data["transport"] in data["transports"]


class TestBaseUrlReflectsRuntime:
    @pytest.mark.asyncio
    async def test_base_url_from_request(self, client):
        data = (await client.get("/discovery")).json()
        # Derived from the request host:port used to reach the server.
        assert data["base_url"] == "http://memhost:8765"

    @pytest.mark.asyncio
    async def test_base_url_env_override(self, client):
        with patch.dict(os.environ,
                        {"OPENMEMORY_DISCOVERY_BASE_URL": "http://192.168.0.10:8765/"}):
            data = (await client.get("/discovery")).json()
        # Override wins and the trailing slash is trimmed.
        assert data["base_url"] == "http://192.168.0.10:8765"


class TestWellKnownAlias:
    @pytest.mark.asyncio
    async def test_well_known_returns_same_payload(self, client):
        a = (await client.get("/discovery")).json()
        b = (await client.get("/.well-known/mcp")).json()
        assert a == b

    @pytest.mark.asyncio
    async def test_payload_is_sufficient_to_build_connection(self, client):
        """Integration-style: the JSON has everything to assemble a real URL."""
        data = (await client.get("/discovery")).json()
        url = data["base_url"] + data["route_template"].format(
            client_name="cursor", user_id="maqA"
        )
        assert url == "http://memhost:8765/mcp/cursor/sse/maqA"
