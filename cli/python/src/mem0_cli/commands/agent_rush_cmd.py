"""mem0 agent-rush — AGENTRUSH game commands.

Wraps the platform's /v1/agent-rush/{memories/, memories/search/} endpoints.
Hardcoded routing; no flags needed.
"""

from __future__ import annotations

import httpx
import typer
from rich.console import Console

from mem0_cli.branding import BRAND_COLOR, print_error, print_success
from mem0_cli.config import load_config

console = Console()
err_console = Console(stderr=True)

_SOURCE_HEADERS = {
    "X-Mem0-Source": "cli",
    "X-Mem0-Client-Language": "python",
    "X-Mem0-Mode": "agent-rush",
}

_ERROR_HINTS = {
    "agentrush_search_first": "Run 3 'mem0 agent-rush search' commands before adding.",
    "agentrush_search_quota": "You've used your 3 lifetime searches.",
    "agentrush_add_quota": "You've used your 3 lifetime adds.",
    "agentrush_not_agent_mode": "Re-run 'mem0 init --agent' to bootstrap an agent-mode key.",
    "agentrush_length": "Memory text must be 50-1000 characters.",
    "agentrush_no_urls": "URLs are not allowed.",
    "agentrush_blocklist": "Content contains a blocked term.",
    "agentrush_global_quota": "Event-wide cap reached. Try again later.",
    "agentrush_not_provisioned": "AGENTRUSH is not provisioned in this environment.",
}


def _call(path: str, body: dict) -> dict:
    config = load_config()
    if not config.platform.api_key:
        print_error(err_console, "Not initialized. Run `mem0 init --agent` first.")
        raise typer.Exit(1)
    base_url = (config.platform.base_url or "https://api.mem0.ai").rstrip("/")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{base_url}{path}",
                headers={
                    **_SOURCE_HEADERS,
                    "Authorization": f"Token {config.platform.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except httpx.HTTPError as exc:
        print_error(err_console, f"Network error: {exc}")
        raise typer.Exit(1) from exc
    try:
        data = resp.json()
    except Exception:
        data = {}
    if resp.status_code >= 400:
        code = (data.get("error") or {}).get("code", "unknown") if isinstance(data, dict) else "unknown"
        print_error(err_console, f"AGENTRUSH error: {code}")
        hint = _ERROR_HINTS.get(code)
        if hint:
            console.print(f"  [dim]{hint}[/dim]")
        raise typer.Exit(1)
    return data


def run_agent_rush_add(content: str) -> None:
    result = _call("/v1/agent-rush/memories/", {"content": content})
    event_id = result.get("event_id", "?")
    print_success(console, f"Memory submitted (event_id: {event_id})")


def run_agent_rush_search(query: str) -> None:
    result = _call("/v1/agent-rush/memories/search/", {"query": query})
    memories = result.get("results") or result.get("memories") or []
    if not memories:
        console.print("[dim](no results)[/dim]")
        return
    for i, m in enumerate(memories[:5], start=1):
        text = m.get("memory") if isinstance(m, dict) else str(m)
        console.print(f"  {i}. {text}")
