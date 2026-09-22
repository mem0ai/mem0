"""Event commands: list and status."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mem0_cli.backend.base import Backend
from mem0_cli.branding import (
    ACCENT_COLOR,
    BRAND_COLOR,
    DIM_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    print_info,
    timed_status,
)
from mem0_cli.output import format_agent_envelope, format_json

console = Console()
err_console = Console(stderr=True)

_STATUS_STYLE = {
    "SUCCEEDED": f"[{SUCCESS_COLOR}]SUCCEEDED[/]",
    "PENDING": f"[{ACCENT_COLOR}]PENDING[/]",
    "FAILED": f"[{ERROR_COLOR}]FAILED[/]",
    "PROCESSING": f"[{WARNING_COLOR}]PROCESSING[/]",
}


def _status_styled(status: str) -> str:
    return _STATUS_STYLE.get(status.upper(), status)


def cmd_event_list(backend: Backend, *, output: str = "table") -> None:
    """List recent background events."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("event list")
    if is_agent_mode():
        output = "agent"
    import time as _time

    _start = _time.perf_counter()
    with timed_status(err_console, "Fetching events...") as _ts:
        try:
            results = backend.list_events()
        except Exception as e:
            _ts.error_msg = str(e)
            raise typer.Exit(1) from None

    _elapsed = _time.perf_counter() - _start

    if output == "agent":
        format_agent_envelope(
            console,
            command="event list",
            data=results,
            count=len(results),
            duration_ms=int(_elapsed * 1000),
        )
        return

    if output == "json":
        format_json(console, results)
        return

    if not results:
        console.print()
        print_info(console, "No events found.")
        console.print()
        return

    table = Table(
        border_style=BRAND_COLOR,
        header_style=f"bold {ACCENT_COLOR}",
        row_styles=["", "dim"],
        padding=(0, 1),
    )
    table.add_column("Event ID", style="dim", max_width=10, no_wrap=True)
    table.add_column("Type", max_width=14)
    table.add_column("Status", max_width=12)
    table.add_column("Latency", max_width=10, justify="right")
    table.add_column("Created", max_width=20)

    for ev in results:
        ev_id = str(ev.get("id", ""))[:8]
        ev_type = str(ev.get("event_type", "—"))
        status = str(ev.get("status", "—"))
        latency = ev.get("latency")
        latency_str = f"{latency:.0f}ms" if isinstance(latency, (int, float)) else "—"
        created = str(ev.get("created_at", "—"))[:19].replace("T", " ")
        table.add_row(ev_id, ev_type, _status_styled(status), latency_str, created)

    console.print()
    console.print(table)
    console.print(f"  [{DIM_COLOR}]{len(results)} event{'s' if len(results) != 1 else ''}[/]")
    console.print()


def cmd_event_status(backend: Backend, event_id: str, *, output: str = "text") -> None:
    """Get the status of a specific background event."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("event status")
    if is_agent_mode():
        output = "agent"
    import time as _time

    _start = _time.perf_counter()
    with timed_status(err_console, "Fetching event...") as _ts:
        try:
            ev = backend.get_event(event_id)
        except Exception as e:
            _ts.error_msg = str(e)
            raise typer.Exit(1) from None

    _elapsed = _time.perf_counter() - _start

    if output == "agent":
        format_agent_envelope(
            console,
            command="event status",
            data=ev,
            duration_ms=int(_elapsed * 1000),
        )
        return

    if output == "json":
        format_json(console, ev)
        return

    status = str(ev.get("status", "—"))
    ev_type = str(ev.get("event_type", "—"))
    latency = ev.get("latency")
    latency_str = f"{latency:.0f}ms" if isinstance(latency, (int, float)) else "—"
    created = str(ev.get("created_at", "—"))[:19].replace("T", " ")
    updated = str(ev.get("updated_at", "—"))[:19].replace("T", " ")
    results = ev.get("results")

    lines = []
    lines.append(f"  [{DIM_COLOR}]Event ID:[/]     {event_id}")
    lines.append(f"  [{DIM_COLOR}]Type:[/]         {ev_type}")
    lines.append(f"  [{DIM_COLOR}]Status:[/]       {_status_styled(status)}")
    lines.append(f"  [{DIM_COLOR}]Latency:[/]      {latency_str}")
    lines.append(f"  [{DIM_COLOR}]Created:[/]      {created}")
    lines.append(f"  [{DIM_COLOR}]Updated:[/]      {updated}")

    if results:
        lines.append("")
        lines.append(f"  [{DIM_COLOR}]Results ({len(results)}):[/]")
        for r in results:
            mem_id = str(r.get("id", ""))[:8]
            data = r.get("data", {})
            memory = data.get("memory", "") if isinstance(data, dict) else str(data)
            ev_name = str(r.get("event", ""))
            user = str(r.get("user_id", ""))
            detail = f"{ev_name}  {memory}"
            if user:
                detail += f"  [{DIM_COLOR}](user_id={user})[/]"
            lines.append(f"    [{SUCCESS_COLOR}]·[/] {detail}  [{DIM_COLOR}]({mem_id})[/]")

    content = "\n".join(lines)
    panel = Panel(
        content,
        title=f"[{BRAND_COLOR}]Event Status[/]",
        title_align="left",
        border_style=BRAND_COLOR,
        padding=(1, 1),
    )
    console.print()
    console.print(panel)
    console.print()
