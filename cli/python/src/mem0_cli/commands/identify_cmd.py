"""mem0 identify — declare which agent owns the current agent-mode key.

Used when `mem0 init --agent` ran without --agent-caller, so the backend
saved agent_caller=NULL. The agent re-runs `mem0 identify <name>` to PATCH
its own row with its real identity. Idempotent — running it again just
overwrites.
"""

from __future__ import annotations

import httpx
import typer
from rich.console import Console

from mem0_cli.branding import print_error, print_success
from mem0_cli.config import load_config, save_config

console = Console()
err_console = Console(stderr=True)

_SOURCE_HEADERS = {
    "X-Mem0-Source": "cli",
    "X-Mem0-Client-Language": "python",
}


def run_identify(name: str) -> None:
    """PATCH the active agent-mode key's agent_caller field."""
    config = load_config()
    if not config.platform.api_key:
        print_error(
            err_console,
            "No API key configured. Run `mem0 init --agent` first.",
        )
        raise typer.Exit(1)
    if not config.platform.agent_mode:
        print_error(
            err_console,
            "This command only works on unclaimed agent-mode keys.",
        )
        raise typer.Exit(1)

    name = (name or "").strip()
    if not name:
        print_error(err_console, "Agent name is required.")
        raise typer.Exit(1)

    base_url = (config.platform.base_url or "https://api.mem0.ai").rstrip("/")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.patch(
                f"{base_url}/api/v1/auth/agent_mode/caller/",
                headers={
                    **_SOURCE_HEADERS,
                    "Authorization": f"Token {config.platform.api_key}",
                    "Content-Type": "application/json",
                },
                json={"agent_caller": name},
            )
    except httpx.HTTPError as exc:
        print_error(err_console, f"Network error: {exc}")
        raise typer.Exit(1) from exc

    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", resp.text)
        except Exception:
            detail = resp.text
        print_error(err_console, f"Identify failed: {detail}")
        raise typer.Exit(1)

    canonical = resp.json().get("agent_caller", name)
    config.platform.agent_caller = canonical
    save_config(config)
    print_success(console, f"Identified as {canonical}.")
