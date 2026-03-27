"""Memory CRUD commands: add, search, get, list, update, delete."""

from __future__ import annotations

import json
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
    format_json,
    format_memories_table,
    format_memories_text,
    format_single_memory,
    print_result_summary,
)

console = Console()
err_console = Console(stderr=True)


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
    enable_graph: bool = False,
    output: str = "text",
) -> None:
    """Add a memory."""
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

    # Read from stdin if no text and stdin is piped
    elif not content and not sys.stdin.isatty():
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
                enable_graph=enable_graph,
            )
        except Exception as e:
            ts.error_msg = str(e)
            print_error(err_console, str(e))
            raise typer.Exit(1) from None

    if output == "quiet":
        return

    if output == "json":
        format_add_result(console, result, output)
        return

    console.print()
    print_scope(console, user_id=user_id, agent_id=agent_id, app_id=app_id, run_id=run_id)
    # Count results
    results = result if isinstance(result, list) else result.get("results", [result])
    count = len(results) if results else 0
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
    enable_graph: bool = False,
    output: str = "text",
) -> None:
    """Search memories."""
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
                enable_graph=enable_graph,
            )
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
    _elapsed = _time.perf_counter() - _start

    if output == "json":
        format_json(console, results)
    elif output == "table":
        if results:
            format_memories_table(console, results)
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
    with timed_status(err_console, "Fetching memory...") as _ts:
        try:
            result = backend.get(memory_id)
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None

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
    enable_graph: bool = False,
    output: str = "table",
) -> None:
    """List memories."""
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
                enable_graph=enable_graph,
            )
        except Exception as e:
            print_error(err_console, str(e))
            raise typer.Exit(1) from None
    _elapsed = _time.perf_counter() - _start

    if output == "json":
        format_json(console, results)
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

    if output == "json":
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

    if output == "json":
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
    if all_:
        # Project-wide wipe using wildcard entity IDs
        if dry_run:
            print_info(console, "Would delete ALL memories project-wide.")
            print_info(console, "No changes made (dry run).")
            return

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

        if output == "json":
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

    if output == "json":
        format_json(console, result)
    elif output != "quiet":
        if isinstance(result, dict) and "message" in result:
            print_info(console, "Deletion started. Memories will be removed in the background.")
        else:
            print_success(console, f"All matching memories deleted ({_elapsed:.2f}s)")
