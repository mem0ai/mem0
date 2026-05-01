"""Memory CRUD commands: add, search, get, list, update, delete."""

from __future__ import annotations

import json
import os
import stat as _stat_mod
import sys
import time as _time
from pathlib import Path

import typer
from rich.console import Console

from mem0_cli.backend.base import Backend
from mem0_cli.branding import (
    print_error,
    print_info,
    print_scope,
    print_success,
    timed_status,
)
from mem0_cli.output import (
    format_add_result,
    format_agent_envelope,
    format_json,
    format_memories_table,
    format_memories_text,
    format_single_memory,
    print_result_summary,
)

console = Console()
err_console = Console(stderr=True)


def _stdin_is_piped() -> bool:
    """Return True only when stdin is an actual pipe or file redirect."""
    from mem0_cli.state import is_agent_mode

    if is_agent_mode():
        return False
    try:
        mode = os.fstat(sys.stdin.fileno()).st_mode
        return _stat_mod.S_ISFIFO(mode) or _stat_mod.S_ISREG(mode)
    except Exception:
        return False


def cmd_add(
    backend: Backend,
    text: str | None,
    *,
    user_id: str | None,
    agent_id: str | None,
    app_id: str | None,
    run_id: str | None,
    messages: str | None,
    file: Path | None,
    metadata: str | None,
    immutable: bool,
    no_infer: bool,
    expires: str | None,
    categories: str | None,
    output: str = "text",
) -> None:
    """Add a memory."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("add")
    if is_agent_mode():
        output = "agent"
    msgs = None
    content = text

    # Read from file
    if file:
        try:
            raw = Path(file).read_text()
            msgs = json.loads(raw)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print_error(err_console, f"Failed to read file: {e}")
            raise typer.Exit(1) from None

    # Parse messages JSON
    elif messages:
        try:
            msgs = json.loads(messages)
        except json.JSONDecodeError as e:
            print_error(err_console, f"Invalid JSON in --messages: {e}")
            raise typer.Exit(1) from None

    # Read from stdin only if stdin is an actual pipe or file redirect
    elif not content and _stdin_is_piped():
        content = sys.stdin.read().strip()

    if not content and not msgs:
        print_error(
            err_console, "No content provided. Pass text, --messages, --file, or pipe via stdin."
        )
        raise typer.Exit(1)

    meta = None
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            print_error(err_console, "Invalid JSON in --metadata.")
            raise typer.Exit(1) from None

    cats = None
    if categories:
        try:
            cats = json.loads(categories)
        except json.JSONDecodeError:
            cats = [c.strip() for c in categories.split(",")]

    # Validate --expires
    if expires:
        import re

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", expires):
            print_error(
                err_console, "Invalid date format for --expires. Use YYYY-MM-DD (e.g. 2025-12-31)."
            )
            raise typer.Exit(1)
        from datetime import date

        if date.fromisoformat(expires) <= date.today():
            print_error(err_console, "--expires date must be in the future.")
            raise typer.Exit(1)

    with timed_status(err_console, "Adding memory...") as ts:
        try:
            result = backend.add(
                content=content,
                messages=msgs,
                user_id=user_id,
                agent_id=agent_id,
                app_id=app_id,
                run_id=run_id,
                metadata=meta,
                immutable=immutable,
                infer=not no_infer,
                expires=expires,
                categories=cats,
            )
        except Exception as e:
            ts.error_msg = str(e)
            raise typer.Exit(1) from None

    if output == "quiet":
        return

    # Deduplicate PENDING entries sharing the same event_id across all output modes
    results_list = result if isinstance(result, list) else result.get("results", [result])
    seen_events: set[str] = set()
    deduped: list[dict] = []
    for r in results_list:
        if r.get("status") == "PENDING":
            eid = r.get("event_id", "")
            if eid and eid in seen_events:
                continue
            if eid:
                seen_events.add(eid)
        deduped.append(r)
    # Write back so downstream formatters see deduplicated data
    if isinstance(result, dict) and "results" in result:
        result = {**result, "results": deduped}
    else:
        result = deduped

    if output == "agent":
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
        format_agent_envelope(
            console,
            command="add",
            data=deduped,
            scope=scope or None,
            count=len(deduped),
        )
        return

    if output == "json":
        format_add_result(console, result, output)
        return

    console.print()
    print_scope(console, user_id=user_id, agent_id=agent_id, app_id=app_id, run_id=run_id)
    count = len(deduped)
    all_pending = count > 0 and all(r.get("status") == "PENDING" for r in deduped)
    if all_pending:
        print_success(
            console,
            f"Memory queued — {count} event{'s' if count != 1 else ''} pending",
        )
    else:
        print_success(
            console, f"Memory processed — {count} memor{'y' if count == 1 else 'ies'} extracted"
        )
    format_add_result(console, result, output)


def cmd_search(
    backend: Backend,
    query: str,
    *,
    user_id: str | None,
    agent_id: str | None,
    app_id: str | None,
    run_id: str | None,
    top_k: int,
    threshold: float,
    rerank: bool,
    keyword: bool,
    filter_json: str | None,
    fields: str | None,
    output: str = "text",
) -> None:
    """Search memories."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("search")
    if is_agent_mode():
        output = "agent"
    filters = None
    if filter_json:
        try:
            filters = json.loads(filter_json)
        except json.JSONDecodeError:
            print_error(err_console, "Invalid JSON in --filter.")
            raise typer.Exit(1) from None

    field_list = None
    if fields:
        field_list = [f.strip() for f in fields.split(",")]

    if top_k < 1:
        print_error(err_console, "--top-k must be >= 1.")
        raise typer.Exit(1)
    if not (0.0 <= threshold <= 1.0):
        print_error(err_console, "--threshold must be between 0.0 and 1.0.")
        raise typer.Exit(1)

    _start = _time.perf_counter()
    with timed_status(err_console, "Searching memories...") as _ts:
        try:
            results = backend.search(
                query,
                user_id=user_id,
                agent_id=agent_id,
                app_id=app_id,
                run_id=run_id,
                top_k=top_k,
                threshold=threshold,
                rerank=rerank,
                keyword=keyword,
                filters=filters,
                fields=field_list,
            )
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
    _elapsed = _time.perf_counter() - _start

    if output == "quiet":
        return

    if output == "agent":
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
        format_agent_envelope(
            console,
            command="search",
            data=results,
            scope=scope or None,
            count=len(results),
            duration_ms=int(_elapsed * 1000),
        )
        return

    if output == "json":
        format_json(console, results)
    elif output == "table":
        if results:
            format_memories_table(console, results, show_score=True)
            print_result_summary(
                console, len(results), duration_secs=_elapsed, user_id=user_id, agent_id=agent_id
            )
        else:
            console.print()
            print_info(console, "No memories found matching your query.")
            console.print()
    else:
        if results:
            format_memories_text(console, results)
            print_result_summary(
                console, len(results), duration_secs=_elapsed, user_id=user_id, agent_id=agent_id
            )
        else:
            console.print()
            print_info(console, "No memories found matching your query.")
            console.print()


def cmd_get(backend: Backend, memory_id: str, *, output: str) -> None:
    """Get a specific memory by ID."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("get")
    if is_agent_mode():
        output = "agent"
    with timed_status(err_console, "Fetching memory...") as _ts:
        try:
            result = backend.get(memory_id)
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None

    if output == "agent":
        format_agent_envelope(console, command="get", data=result)
    else:
        format_single_memory(console, result, output)


def cmd_list(
    backend: Backend,
    *,
    user_id: str | None,
    agent_id: str | None,
    app_id: str | None,
    run_id: str | None,
    page: int,
    page_size: int,
    category: str | None,
    after: str | None,
    before: str | None,
    output: str = "table",
) -> None:
    """List memories."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("list")
    if is_agent_mode():
        output = "agent"
    if page_size < 1:
        print_error(err_console, "--page-size must be >= 1.")
        raise typer.Exit(1)
    if page < 1:
        print_error(err_console, "--page must be >= 1.")
        raise typer.Exit(1)

    _start = _time.perf_counter()
    with timed_status(err_console, "Listing memories...") as _ts:
        try:
            results = backend.list_memories(
                user_id=user_id,
                agent_id=agent_id,
                app_id=app_id,
                run_id=run_id,
                page=page,
                page_size=page_size,
                category=category,
                after=after,
                before=before,
            )
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
    _elapsed = _time.perf_counter() - _start

    if output == "quiet":
        return

    if output in ("json", "agent"):
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
        format_agent_envelope(
            console,
            command="list",
            data=results,
            scope=scope or None,
            count=len(results),
            duration_ms=int(_elapsed * 1000),
        )
    elif output == "table":
        if results:
            format_memories_table(console, results)
            print_result_summary(
                console,
                len(results),
                duration_secs=_elapsed,
                page=page,
                user_id=user_id,
                agent_id=agent_id,
            )
        else:
            console.print()
            print_info(console, "No memories found.")
            console.print()
    else:
        if results:
            format_memories_text(console, results, title="memories")
            print_result_summary(
                console,
                len(results),
                duration_secs=_elapsed,
                page=page,
                user_id=user_id,
                agent_id=agent_id,
            )
        else:
            console.print()
            print_info(console, "No memories found.")
            console.print()


def cmd_update(
    backend: Backend,
    memory_id: str,
    text: str | None,
    *,
    metadata: str | None,
    output: str,
) -> None:
    """Update a memory."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("update")
    if is_agent_mode():
        output = "agent"
    meta = None
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            print_error(err_console, "Invalid JSON in --metadata.")
            raise typer.Exit(1) from None

    _start = _time.perf_counter()
    with timed_status(err_console, "Updating memory...") as _ts:
        try:
            result = backend.update(memory_id, content=text, metadata=meta)
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
    _elapsed = _time.perf_counter() - _start

    if output == "agent":
        format_agent_envelope(
            console,
            command="update",
            data=result,
            duration_ms=int(_elapsed * 1000),
        )
    elif output == "json":
        format_json(console, result)
    elif output != "quiet":
        print_success(console, f"Memory {memory_id[:8]} updated ({_elapsed:.2f}s)")


def cmd_delete(
    backend: Backend,
    memory_id: str,
    *,
    dry_run: bool = False,
    force: bool = False,
    output: str,
) -> None:
    """Delete a single memory by ID."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("delete")
    if is_agent_mode():
        output = "agent"
    if dry_run:
        # Fetch and display what would be deleted
        try:
            mem = backend.get(memory_id)
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
        format_single_memory(console, mem, output)
        print_info(console, "No changes made (dry run).")
        return

    _start = _time.perf_counter()
    with timed_status(err_console, "Deleting...") as _ts:
        try:
            result = backend.delete(memory_id=memory_id)
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
    _elapsed = _time.perf_counter() - _start

    if output == "agent":
        format_agent_envelope(
            console,
            command="delete",
            data={"id": memory_id, "deleted": True},
            duration_ms=int(_elapsed * 1000),
        )
    elif output == "json":
        format_json(console, result)
    elif output != "quiet":
        print_success(console, f"Memory {memory_id[:8]} deleted ({_elapsed:.2f}s)")


def cmd_delete_all(
    backend: Backend,
    *,
    force: bool,
    dry_run: bool = False,
    all_: bool = False,
    user_id: str | None,
    agent_id: str | None,
    app_id: str | None,
    run_id: str | None,
    output: str,
) -> None:
    """Delete all memories matching a scope."""
    from mem0_cli.state import is_agent_mode, set_current_command

    set_current_command("delete-all")
    if is_agent_mode():
        output = "agent"
        if not force:
            print_error(err_console, "Destructive operation requires --force in agent mode.")
            raise typer.Exit(1)
    if all_:
        # Project-wide wipe using wildcard entity IDs
        # Note: --dry-run is ignored here because the API has no count-before-delete endpoint.

        if not force:
            confirm = typer.confirm(
                "\n  ⚠  Delete ALL memories across the ENTIRE project? This cannot be undone."
            )
            if not confirm:
                print_info(console, "Cancelled.")
                raise typer.Exit(0)

        _start = _time.perf_counter()
        with timed_status(err_console, "Deleting all memories project-wide...") as _ts:
            try:
                result = backend.delete(
                    all=True,
                    user_id="*",
                    agent_id="*",
                    app_id="*",
                    run_id="*",
                )
            except Exception as e:
                print_error(err_console, str(e))
                raise typer.Exit(1) from None
        _elapsed = _time.perf_counter() - _start

        if output == "agent":
            format_agent_envelope(
                console,
                command="delete-all",
                data={"deleted": True, "scope": "project"},
                duration_ms=int(_elapsed * 1000),
            )
        elif output == "json":
            format_json(console, result)
        elif output != "quiet":
            if isinstance(result, dict) and "message" in result:
                print_info(console, "Deletion started. Memories will be removed in the background.")
            else:
                print_success(console, f"All project memories deleted ({_elapsed:.2f}s)")
        return

    if dry_run:
        # List matching memories and show count
        try:
            results = backend.list_memories(
                user_id=user_id,
                agent_id=agent_id,
                app_id=app_id,
                run_id=run_id,
            )
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
        count = len(results)
        print_info(console, f"Would delete {count} memor{'y' if count == 1 else 'ies'}.")
        print_info(console, "No changes made (dry run).")
        return

    if not force:
        scope_parts = []
        if user_id:
            scope_parts.append(f"user={user_id}")
        if agent_id:
            scope_parts.append(f"agent={agent_id}")
        if app_id:
            scope_parts.append(f"app={app_id}")
        if run_id:
            scope_parts.append(f"run={run_id}")
        scope = ", ".join(scope_parts) if scope_parts else "ALL entities"

        confirm = typer.confirm(f"\n  ⚠  Delete ALL memories for {scope}? This cannot be undone.")
        if not confirm:
            print_info(console, "Cancelled.")
            raise typer.Exit(0)

    _start = _time.perf_counter()
    with timed_status(err_console, "Deleting all memories...") as _ts:
        try:
            result = backend.delete(
                all=True,
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
            command="delete-all",
            data={"deleted": True},
            scope=scope or None,
            duration_ms=int(_elapsed * 1000),
        )
    elif output == "json":
        format_json(console, result)
    elif output != "quiet":
        if isinstance(result, dict) and "message" in result:
            print_info(console, "Deletion started. Memories will be removed in the background.")
        else:
            print_success(console, f"All matching memories deleted ({_elapsed:.2f}s)")
