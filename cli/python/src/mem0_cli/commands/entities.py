"""Entity management commands."""

from __future__ import annotations

import time as _time

import typer
from rich.console import Console
from rich.table import Table

from mem0_cli.backend.base import Backend
from mem0_cli.branding import (
    ACCENT_COLOR,
    BRAND_COLOR,
    DIM_COLOR,
    print_error,
    print_info,
    print_success,
    timed_status,
)
from mem0_cli.output import format_agent_envelope, format_json

console = Console()
err_console = Console(stderr=True)


def cmd_entities_list(backend: Backend, entity_type: str, *, output: str) -> None:
    """List entities of a given type."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("entity list")
    if is_agent_mode():
        output = "agent"
    valid_types = {"users", "agents", "apps", "runs"}
    if entity_type not in valid_types:
        print_error(
            err_console, f"Invalid entity type: {entity_type}. Use: {', '.join(valid_types)}"
        )
        raise typer.Exit(1)

    _start = _time.perf_counter()
    with timed_status(err_console, f"Fetching {entity_type}...") as _ts:
        try:
            results = backend.entities(entity_type)
        except Exception as e:
            print_error(err_console, str(e), hint="This feature may require the mem0 Platform.")
            raise typer.Exit(1) from None
    _elapsed = _time.perf_counter() - _start

    if output == "agent":
        format_agent_envelope(
            console,
            command="entity list",
            data=results,
            count=len(results),
            duration_ms=int(_elapsed * 1000),
        )
        return

    if output == "json":
        format_json(console, results)
        return

    if not results:
        print_info(console, f"No {entity_type} found.")
        return

    table = Table(border_style=BRAND_COLOR, header_style=f"bold {ACCENT_COLOR}", padding=(0, 1))
    table.add_column("Name / ID", style="bold")
    table.add_column("Created", max_width=12)

    for entity in results:
        name = entity.get("name", entity.get("id", "—"))
        created = str(entity.get("created_at", "—"))[:10]
        table.add_row(str(name), created)

    console.print()
    console.print(table)
    console.print(f"  [{DIM_COLOR}]{len(results)} {entity_type} ({_elapsed:.2f}s)[/]")
    console.print()


def cmd_entities_delete(
    backend: Backend,
    *,
    user_id: str | None,
    agent_id: str | None,
    app_id: str | None,
    run_id: str | None,
    force: bool,
    dry_run: bool = False,
    output: str,
) -> None:
    """Delete an entity and all its memories (cascade delete)."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("entity delete")
    if is_agent_mode():
        output = "agent"
        if not force:
            print_error(err_console, "Destructive operation requires --force in agent mode.")
            raise typer.Exit(1)
    if not any([user_id, agent_id, app_id, run_id]):
        print_error(
            err_console, "Provide at least one of --user-id, --agent-id, --app-id, --run-id."
        )
        raise typer.Exit(1)

    scope_parts = []
    if user_id:
        scope_parts.append(f"user={user_id}")
    if agent_id:
        scope_parts.append(f"agent={agent_id}")
    if app_id:
        scope_parts.append(f"app={app_id}")
    if run_id:
        scope_parts.append(f"run={run_id}")
    scope_str = ", ".join(scope_parts)

    if dry_run:
        print_info(console, f"Would delete entity {scope_str} and all its memories.")
        print_info(console, "No changes made (dry run).")
        return

    if not force:
        confirm = typer.confirm(
            f"\n  \u26a0  Delete entity {scope_str} AND all its memories? This cannot be undone."
        )
        if not confirm:
            print_info(console, "Cancelled.")
            raise typer.Exit(0)

    _start = _time.perf_counter()
    with timed_status(err_console, "Deleting entity...") as _ts:
        try:
            result = backend.delete_entities(
                user_id=user_id,
                agent_id=agent_id,
                app_id=app_id,
                run_id=run_id,
            )
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
    _elapsed = _time.perf_counter() - _start

    scope = {
        k: v
        for k, v in {
            "user_id": user_id,
            "agent_id": agent_id,
            "app_id": app_id,
            "run_id": run_id,
        }.items()
        if v
    }
    if output == "agent":
        format_agent_envelope(
            console,
            command="entity delete",
            data={"deleted": True},
            scope=scope or None,
            duration_ms=int(_elapsed * 1000),
        )
    elif output == "json":
        format_json(console, result)
    elif output != "quiet":
        print_success(console, f"Entity deleted with all memories ({_elapsed:.2f}s)")
