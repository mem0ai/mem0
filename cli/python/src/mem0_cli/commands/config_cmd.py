"""Config management commands: show, set, get."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from mem0_cli.branding import ACCENT_COLOR, BRAND_COLOR, DIM_COLOR, print_error, print_success
from mem0_cli.config import (
    get_nested_value,
    load_config,
    redact_key,
    save_config,
    set_nested_value,
)

console = Console()
err_console = Console(stderr=True)


def cmd_config_show(*, output: str = "text") -> None:
    """Display current configuration (secrets redacted)."""
    from mem0_cli.output import format_agent_envelope
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("config show")
    if is_agent_mode():
        output = "agent"

    config = load_config()

    if output in ("json", "agent"):
        format_agent_envelope(
            console,
            command="config show",
            data={
                "defaults": {
                    "user_id": config.defaults.user_id or None,
                    "agent_id": config.defaults.agent_id or None,
                    "app_id": config.defaults.app_id or None,
                    "run_id": config.defaults.run_id or None,
                },
                "platform": {
                    "api_key": redact_key(config.platform.api_key),
                    "base_url": config.platform.base_url,
                },
            },
        )
        return

    console.print()
    console.print(f"  [{BRAND_COLOR}]◆ mem0 Configuration[/]\n")

    table = Table(border_style=BRAND_COLOR, header_style=f"bold {ACCENT_COLOR}", padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    # Defaults
    table.add_row(
        "defaults.user_id",
        config.defaults.user_id or f"[{DIM_COLOR}](not set)[/]",
    )
    table.add_row(
        "defaults.agent_id",
        config.defaults.agent_id or f"[{DIM_COLOR}](not set)[/]",
    )
    table.add_row(
        "defaults.app_id",
        config.defaults.app_id or f"[{DIM_COLOR}](not set)[/]",
    )
    table.add_row(
        "defaults.run_id",
        config.defaults.run_id or f"[{DIM_COLOR}](not set)[/]",
    )
    table.add_row("", "")

    # Platform
    table.add_row("[bold]platform.api_key[/]", redact_key(config.platform.api_key))
    table.add_row("platform.base_url", config.platform.base_url)

    console.print(table)
    console.print()


def cmd_config_get(key: str) -> None:
    """Get a config value."""
    from mem0_cli.output import format_agent_envelope
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("config get")
    config = load_config()
    value = get_nested_value(config, key)

    if value is None:
        print_error(err_console, f"Unknown config key: {key}")
        return

    display_value = (
        redact_key(str(value)) if ("api_key" in key or "key" in key.split(".")[-1:]) else str(value)
    )

    if is_agent_mode():
        format_agent_envelope(
            console, command="config get", data={"key": key, "value": display_value}
        )
    else:
        console.print(display_value)


def cmd_config_set(key: str, value: str) -> None:
    """Set a config value."""
    from mem0_cli.output import format_agent_envelope
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("config set")
    config = load_config()
    if set_nested_value(config, key, value):
        save_config(config)
        display = redact_key(value) if "key" in key else value
        if is_agent_mode():
            format_agent_envelope(
                console, command="config set", data={"key": key, "value": display}
            )
        else:
            print_success(console, f"{key} = {display}")
    else:
        print_error(err_console, f"Unknown config key: {key}")
