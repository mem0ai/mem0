"""MCP connection auto-discovery endpoint (task_08 / ADR-005).

Exposes a GET endpoint that returns a ready-to-use MCP connection config as
JSON so agents can self-configure without manual setup. The payload mirrors the
real MCP route registered in ``app.mcp_server`` (``/mcp/{client_name}/sse/{user_id}``
and the Streamable HTTP variant) and the field semantics defined by tasks 04/07:
``user_id`` carries the machine hostname (attribution only) and ``project`` is
required and scopes the memory.

The ``base_url`` reflects runtime: it is taken from the ``OPENMEMORY_DISCOVERY_BASE_URL``
environment override when set, otherwise derived from the incoming request, so
the value an agent receives is the address it actually used to reach the server.
"""

import os

from fastapi import APIRouter, Request

router = APIRouter(prefix="", tags=["discovery"])

# Route templates of the MCP transports registered in app.mcp_server. Kept in
# sync with the `/mcp` router there; the segments are the fields the agent fills.
_SSE_ROUTE_TEMPLATE = "/mcp/{client_name}/sse/{user_id}"
_HTTP_ROUTE_TEMPLATE = "/mcp/{client_name}/http/{user_id}"

# Default transport advertised at the top level (SSE remains the widely-supported
# default); both enabled transports are listed under "transports".
_DEFAULT_TRANSPORT = "sse"


def _base_url(request: Request) -> str:
    """Resolve the server base URL, honoring an explicit env override.

    Falls back to the incoming request's base URL so the advertised address
    matches how the client reached the server (reflecting runtime config).
    """
    override = os.getenv("OPENMEMORY_DISCOVERY_BASE_URL")
    if override:
        return override.rstrip("/")
    return str(request.base_url).rstrip("/")


def _discovery_payload(request: Request) -> dict:
    return {
        "transport": _DEFAULT_TRANSPORT,
        "base_url": _base_url(request),
        "route_template": _SSE_ROUTE_TEMPLATE,
        "transports": {
            "sse": _SSE_ROUTE_TEMPLATE,
            "http": _HTTP_ROUTE_TEMPLATE,
        },
        "fields": {
            "client_name": "MCP client/agent name",
            "user_id": "hostname",
            "project": "obrigatório",
        },
    }


@router.get("/discovery")
async def get_discovery(request: Request) -> dict:
    """Return the MCP connection config as JSON for agent self-configuration."""
    return _discovery_payload(request)


@router.get("/.well-known/mcp")
async def get_well_known_mcp(request: Request) -> dict:
    """Alias of :func:`get_discovery` on the conventional well-known path."""
    return _discovery_payload(request)
