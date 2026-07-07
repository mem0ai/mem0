"""Branding and ASCII art for mem0 CLI."""

import os
import sys
import time
from contextlib import contextmanager

from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

# stderr console for spinners, errors, and timing messages
_err = Console(stderr=True)

LOGO = r"""
███╗   ███╗███████╗███╗   ███╗ ██████╗      ██████╗██╗     ██╗
████╗ ████║██╔════╝████╗ ████║██╔═████╗    ██╔════╝██║     ██║
██╔████╔██║█████╗  ██╔████╔██║██║██╔██║    ██║     ██║     ██║
██║╚██╔╝██║██╔══╝  ██║╚██╔╝██║████╔╝██║    ██║     ██║     ██║
██║ ╚═╝ ██║███████╗██║ ╚═╝ ██║╚██████╔╝    ╚██████╗███████╗██║
╚═╝     ╚═╝╚══════╝╚═╝     ╚═╝ ╚═════╝      ╚═════╝╚══════╝╚═╝
"""

LOGO_MINI = "◆ mem0"

TAGLINE = "The Memory Layer for AI Agents"

BRAND_COLOR = "#8b5cf6"  # Purple
ACCENT_COLOR = "#a78bfa"
SUCCESS_COLOR = "#22c55e"
ERROR_COLOR = "#ef4444"
WARNING_COLOR = "#f59e0b"
DIM_COLOR = "#6b7280"


def _sym(fancy: str, plain: str) -> str:
    """Return *fancy* when stdout is a TTY with colour, else *plain*."""
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR") is not None:
        return plain
    return fancy


def print_banner(console: Console) -> None:
    """Print the mem0 welcome banner."""
    from mem0_cli.state import is_agent_mode

    if is_agent_mode():
        return
    logo_text = Text(LOGO, style=f"bold {BRAND_COLOR}")
    tagline = Text(f"  {TAGLINE}\n", style=f"{ACCENT_COLOR}")

    content = Text()
    content.append_text(logo_text)
    content.append_text(tagline)

    panel = Panel(
        content,
        border_style=BRAND_COLOR,
        padding=(0, 2),
        subtitle=f"[{DIM_COLOR}]Python SDK · v{_get_version()}[/]",
        subtitle_align="right",
    )
    console.print(panel)


def print_success(console: Console, message: str) -> None:
    from mem0_cli.state import is_agent_mode

    if is_agent_mode():
        return
    sym = _sym("✓", "[ok]")
    console.print(f"[{SUCCESS_COLOR}]{sym}[/] {message}")


def print_error(console: Console, message: str, hint: str | None = None) -> None:
    from mem0_cli.state import get_current_command, is_agent_mode

    if is_agent_mode():
        import json as _json

        envelope = {
            "status": "error",
            "command": get_current_command(),
            "error": message,
            "data": None,
        }
        print(_json.dumps(envelope))
        return
    from rich.markup import escape

    sym = _sym("✗", "[error]")
    console.print(f"[{ERROR_COLOR}]{sym} Error:[/] {escape(str(message))}")
    if hint:
        console.print(f"  [{DIM_COLOR}]{escape(str(hint))}[/]")


def print_warning(console: Console, message: str) -> None:
    from mem0_cli.state import is_agent_mode

    if is_agent_mode():
        return
    sym = _sym("⚠", "[warn]")
    console.print(f"[{WARNING_COLOR}]{sym}[/] {message}")


def print_info(console: Console, message: str) -> None:
    from mem0_cli.state import is_agent_mode

    if is_agent_mode():
        return
    sym = _sym("◆", "*")
    console.print(f"[{BRAND_COLOR}]{sym}[/] {message}")


@contextmanager
def timed_status(console: Console, message: str):
    """Spinner with automatic timing. Yields a context object for setting the final message.

    The spinner and timing output are sent to stderr (via ``_err``) so they
    never contaminate machine-readable stdout.  The *console* parameter is
    kept for backward compatibility but is not used for spinner output.
    In agent mode the spinner is suppressed entirely.
    """
    from mem0_cli.state import is_agent_mode

    class _Ctx:
        def __init__(self):
            self.success_msg = ""
            self.error_msg = ""

    ctx = _Ctx()
    if is_agent_mode():
        try:
            yield ctx
        except Exception:
            raise
        return

    start = time.perf_counter()
    try:
        with Status(f"[{DIM_COLOR}]{message}[/]", console=_err):
            yield ctx
    except Exception:
        elapsed = time.perf_counter() - start
        if ctx.error_msg:
            print_error(_err, f"{ctx.error_msg} ({elapsed:.2f}s)")
            if "Authentication failed" in ctx.error_msg:
                _err.print(
                    f"  [{DIM_COLOR}]Run [bold]mem0 init[/bold] to reconfigure your API key"
                    f" · [bold]https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=cli-python[/bold][/]"
                )
        raise
    else:
        elapsed = time.perf_counter() - start
        if ctx.success_msg:
            print_success(_err, f"{ctx.success_msg} ({elapsed:.2f}s)")


def print_scope(console: Console, **ids: str | None) -> None:
    """Show active entity scope if any IDs are set."""
    from mem0_cli.state import is_agent_mode

    if is_agent_mode():
        return
    parts = []
    for key, val in ids.items():
        if val:
            parts.append(f"{key}={val}")
    if parts:
        scope_str = ", ".join(parts)
        console.print(f"  [{DIM_COLOR}]Scope: {scope_str}[/]")


def _get_version() -> str:
    from mem0_cli import __version__

    return __version__
