"""mem0 init — interactive setup wizard."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.prompt import Prompt

from mem0_cli.branding import (
    BRAND_COLOR,
    DIM_COLOR,
    print_banner,
    print_error,
    print_info,
    print_success,
)
from mem0_cli.config import Mem0Config, save_config

console = Console()
err_console = Console(stderr=True)


def _prompt_secret(label: str) -> str:
    """Prompt for a secret value, echoing '*' for each character typed."""
    sys.stdout.write(label)
    sys.stdout.flush()

    chars: list[str] = []

    if sys.platform == "win32":
        import msvcrt

        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                break
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\x08", "\x7f"):  # backspace
                if chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            else:
                chars.append(ch)
                sys.stdout.write("*")
                sys.stdout.flush()
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\r", "\n"):
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    break
                if ch == "\x03":
                    raise KeyboardInterrupt
                if ch in ("\x7f", "\x08"):  # backspace/delete
                    if chars:
                        chars.pop()
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                elif ch == "\x15":  # Ctrl+U — clear line
                    sys.stdout.write("\b \b" * len(chars))
                    sys.stdout.flush()
                    chars = []
                elif ch >= " ":  # ignore other control characters
                    chars.append(ch)
                    sys.stdout.write("*")
                    sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return "".join(chars)


def run_init(*, api_key: str | None = None, user_id: str | None = None) -> None:
    """Interactive setup wizard for mem0 CLI.

    When both *api_key* and *user_id* are supplied, all prompts are skipped
    (non-interactive mode).  When running in a non-TTY without the required
    flags, an error message is printed.
    """
    config = Mem0Config()

    # Fully non-interactive when both flags provided
    if api_key and user_id:
        config.platform.api_key = api_key
        config.defaults.user_id = user_id
        _validate_platform(config)
        save_config(config)
        print_success(console, "Configuration saved to ~/.mem0/config.json")
        return

    # Non-TTY without full flags -> error
    if not sys.stdin.isatty():
        if not api_key or not user_id:
            print_error(
                err_console,
                "Non-interactive terminal detected and required flags missing.",
                hint="Run: mem0 init --api-key <key> --user-id <id>",
            )
            raise typer.Exit(1)

    print_banner(console)
    console.print()
    print_info(console, "Welcome! Let's set up your mem0 CLI.\n")

    # Use provided flags or prompt
    if api_key:
        config.platform.api_key = api_key
    else:
        _setup_platform(config)

    if user_id:
        config.defaults.user_id = user_id
    else:
        _setup_defaults(config)

    _validate_platform(config)

    save_config(config)
    console.print()
    print_success(console, "Configuration saved to ~/.mem0/config.json")
    console.print()
    console.print(f"  [{DIM_COLOR}]Get started:[/]")
    if config.defaults.user_id:
        console.print(f'  [{DIM_COLOR}]  mem0 add "I prefer dark mode"[/]')
        console.print(f'  [{DIM_COLOR}]  mem0 search "preferences"[/]')
    else:
        console.print(f'  [{DIM_COLOR}]  mem0 add "I prefer dark mode" --user-id alice[/]')
        console.print(f'  [{DIM_COLOR}]  mem0 search "preferences" --user-id alice[/]')
    console.print()


def _setup_platform(config: Mem0Config) -> None:
    """Platform setup flow."""
    console.print()
    console.print(f"  [{DIM_COLOR}]Get your API key at https://app.mem0.ai/dashboard/api-keys[/]")
    console.print()

    console.print(f"  [{BRAND_COLOR}]API Key[/]: ", end="")
    api_key = _prompt_secret("")
    if not api_key:
        print_error(err_console, "API key is required.")
        raise typer.Exit(1)

    config.platform.api_key = api_key


def _setup_defaults(config: Mem0Config) -> None:
    """Collect default entity IDs."""
    console.print()
    print_info(console, "Set default entity IDs (press Enter to skip).\n")

    user_id = Prompt.ask(
        f"  [{BRAND_COLOR}]Default User ID[/] [{DIM_COLOR}](recommended)[/]",
        default="mem0-cli",
    )
    if user_id:
        config.defaults.user_id = user_id


def _validate_platform(config: Mem0Config) -> None:
    """Validate platform connection after all inputs are collected."""
    console.print()
    print_info(console, "Validating connection...")
    try:
        from mem0_cli.backend.platform import PlatformBackend

        backend = PlatformBackend(config.platform)
        status = backend.status(
            user_id=config.defaults.user_id or None,
            agent_id=config.defaults.agent_id or None,
        )
        if status.get("connected"):
            print_success(console, "Connected to mem0 Platform!")
        else:
            print_error(
                err_console,
                f"Could not connect: {status.get('error', 'Unknown error')}",
                hint="Check your API key and try again.",
            )
    except Exception as e:
        print_error(err_console, f"Connection test failed: {e}")
