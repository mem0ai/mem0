"""mem0 agent-rush — AGENTRUSH game commands.

Wraps the platform's /v1/agent-rush/{memories/, memories/search/} endpoints.
Hardcoded routing; no flags needed.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import httpx
import typer
from rich.console import Console

from mem0_cli.branding import print_error, print_success
from mem0_cli.config import load_config, save_config

console = Console()
err_console = Console(stderr=True)

_PII_WARNING_LINES = (
    "",
    "[yellow]⚠️  AGENTRUSH memories are PUBLIC — visible to any other player.[/yellow]",
    "[yellow]   Do not include real names, emails, secrets, work content, or PII.[/yellow]",
    "",
)

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
        code = (
            (data.get("error") or {}).get("code", "unknown")
            if isinstance(data, dict)
            else "unknown"
        )
        print_error(err_console, f"AGENTRUSH error: {code}")
        hint = _ERROR_HINTS.get(code)
        if hint:
            console.print(f"  [dim]{hint}[/dim]")
        raise typer.Exit(1)
    return data


def _ensure_warning_acknowledged() -> None:
    """Block the first interactive add on the PII warning; pass-through for agents.

    Interactive (TTY): show prompt, require explicit 'y', persist
    `agent_rush.acknowledged_at` so we never ask the same machine twice.

    Non-interactive (no TTY — typical when an agent runs the CLI): surface
    the warning to stderr for the human reading the agent transcript and
    proceed without prompting (agents can't answer y/N).
    """
    config = load_config()
    if config.agent_rush.acknowledged_at:
        return

    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    if not is_tty:
        for line in _PII_WARNING_LINES:
            err_console.print(line)
        return

    for line in _PII_WARNING_LINES:
        console.print(line)
    answer = typer.prompt("   Continue? [y/N]", default="N", show_default=False).strip().lower()
    if answer not in ("y", "yes"):
        print_error(err_console, "Aborted.")
        raise typer.Exit(1)

    config.agent_rush.acknowledged_at = datetime.now(timezone.utc).isoformat()
    save_config(config)


def run_agent_rush_add(content: str) -> None:
    _ensure_warning_acknowledged()
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
