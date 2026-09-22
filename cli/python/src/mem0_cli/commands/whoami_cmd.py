"""mem0 whoami — print the active agent's default_user_id (AGENTRUSH identifier)."""

from __future__ import annotations

import typer
from rich.console import Console

from mem0_cli.branding import BRAND_COLOR, print_error, print_info
from mem0_cli.config import load_config

console = Console()
err_console = Console(stderr=True)


def run_whoami() -> None:
    config = load_config()
    session_id = config.platform.default_user_id if config.platform else None
    if not session_id:
        print_error(
            err_console,
            "No default_user_id found. Run `mem0 init --agent` first.",
        )
        raise typer.Exit(1)
    console.print(f"Your AGENTRUSH identifier:  [{BRAND_COLOR}]{session_id}[/{BRAND_COLOR}]")
    print_info(console, "Find your row at https://mem0.ai/agentrush")
