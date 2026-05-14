"""Main CLI application — the entrypoint for `mem0`."""

from __future__ import annotations

import contextlib
import json as _json
import os
import stat as _stat_mod
import sys
from pathlib import Path

import typer
from rich.console import Console

from mem0_cli import __version__
from mem0_cli.branding import BRAND_COLOR, print_error, print_warning

console = Console()
err_console = Console(stderr=True)

# ── Main app ──────────────────────────────────────────────────────────────

app = typer.Typer(
    name="mem0",
    help=f"◆ Mem0 CLI v{__version__} · Python SDK\n\n   The Memory Layer for AI Agents",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
    add_completion=False,
    subcommand_metavar="<command> [options]",
    options_metavar="",
)

# ── Sub-groups (defined here, registered later to control help ordering) ──

config_app = typer.Typer(
    name="config",
    help="Manage mem0 configuration.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

entity_app = typer.Typer(
    name="entity",
    help="Manage entities.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

event_app = typer.Typer(
    name="event",
    help="Inspect background processing events.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
# entity_app and event_app registered after Memory commands to control panel ordering


# ── Validated user identity (set by _get_backend_and_config) ──────────────

_validated_user_email: str | None = None

# ── Telemetry helper ─────────────────────────────────────────────────────


def _fire_telemetry(command_name: str, extra: dict | None = None) -> None:
    """Fire a PostHog telemetry event (non-blocking, never fails)."""
    try:
        from mem0_cli.telemetry import capture_event

        props = {"command": command_name}
        if extra:
            props.update(extra)
        capture_event(f"cli.{command_name}", props, pre_resolved_email=_validated_user_email)
    except Exception:
        pass


@config_app.callback(invoke_without_command=True)
def _config_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand:
        _fire_telemetry(f"config.{ctx.invoked_subcommand}")


@entity_app.callback(invoke_without_command=True)
def _entity_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand:
        _fire_telemetry(f"entity.{ctx.invoked_subcommand}")


@event_app.callback(invoke_without_command=True)
def _event_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand:
        _fire_telemetry(f"event.{ctx.invoked_subcommand}")


# ── Helpers ───────────────────────────────────────────────────────────────


def _get_backend_and_config(
    api_key: str | None = None,
    base_url: str | None = None,
):
    """Build and return the Platform backend plus the loaded config.

    Validates the API key upfront via ``/v1/ping/`` and caches the
    resolved user email for telemetry.
    """
    global _validated_user_email

    from mem0_cli.backend import get_backend
    from mem0_cli.backend.platform import AuthError
    from mem0_cli.config import load_config, save_config

    config = load_config()

    if api_key:
        config.platform.api_key = api_key
    if base_url:
        config.platform.base_url = base_url

    if not config.platform.api_key:
        print_error(
            err_console,
            "No API key configured.",
            hint="Run 'mem0 init' or set MEM0_API_KEY environment variable.",
        )
        raise typer.Exit(1)

    backend = get_backend(config)

    # Validate the API key upfront with a fast timeout
    try:
        ping_data = backend.ping(timeout=5.0)
        email = ping_data.get("user_email") if isinstance(ping_data, dict) else None
        if email:
            _validated_user_email = email
            if config.platform.user_email != email:
                config.platform.user_email = email
                with contextlib.suppress(Exception):
                    save_config(config)
    except AuthError:
        print_error(
            err_console,
            "Invalid or expired API key.",
            hint="Run 'mem0 init' or set MEM0_API_KEY environment variable.",
        )
        raise typer.Exit(1) from None
    except Exception:
        print_warning(err_console, "Could not validate API key (network issue). Proceeding anyway.")

    return backend, config


def _get_backend(
    api_key: str | None = None,
    base_url: str | None = None,
):
    """Build and return the Platform backend."""
    backend, _config = _get_backend_and_config(api_key, base_url)
    return backend


def _resolve_ids(
    config,
    *,
    user_id: str | None = None,
    agent_id: str | None = None,
    app_id: str | None = None,
    run_id: str | None = None,
):
    """Resolve entity IDs: CLI flag > config default > None.

    If any explicit ID is provided, only use explicit IDs (don't mix
    in defaults for other entity types which would over-filter).
    If no explicit IDs, fall back to all configured defaults.
    """
    has_explicit = any([user_id, agent_id, app_id, run_id])
    if has_explicit:
        return {
            "user_id": user_id or None,
            "agent_id": agent_id or None,
            "app_id": app_id or None,
            "run_id": run_id or None,
        }
    return {
        "user_id": config.defaults.user_id or None,
        "agent_id": config.defaults.agent_id or None,
        "app_id": config.defaults.app_id or None,
        "run_id": config.defaults.run_id or None,
    }


def _stdin_is_piped() -> bool:
    """Return True only when stdin is an actual pipe or file redirect — not a bare open fd."""
    from mem0_cli.state import is_agent_mode

    if is_agent_mode():
        return False
    try:
        mode = os.fstat(sys.stdin.fileno()).st_mode
        return _stat_mod.S_ISFIFO(mode) or _stat_mod.S_ISREG(mode)
    except Exception:
        return False


def _read_stdin() -> str | None:
    """Read from stdin if it is an actual pipe or file redirect (not a TTY, not agent mode)."""
    if _stdin_is_piped():
        return sys.stdin.read().strip() or None
    return None


# ── Global options (shared via callback) ──────────────────────────────────


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
    json_agent: bool = typer.Option(
        False,
        "--json",
        "--agent",
        help="Output as JSON for agent/programmatic use.",
        is_eager=False,
    ),
) -> None:
    if json_agent:
        from mem0_cli.state import set_agent_mode

        set_agent_mode(True)
    if version:
        from mem0_cli.commands.utils import cmd_version

        _fire_telemetry("version")
        cmd_version()
        raise typer.Exit()
    if ctx.invoked_subcommand:
        # Stash the active subcommand name so the JSON error envelope
        # (print_error in agent mode) can report which command failed
        # instead of an empty `"command": ""` field.
        from mem0_cli.state import set_current_command

        set_current_command(ctx.invoked_subcommand)
    if ctx.invoked_subcommand and ctx.invoked_subcommand != "init":
        # init fires its own telemetry from init_cmd.run_init with full M1-M6 props.
        _fire_telemetry(ctx.invoked_subcommand)


# ── Memory: add ───────────────────────────────────────────────────────────


@app.command(rich_help_panel="Memory")
def add(
    text: str | None = typer.Argument(None, help="Text content to add as a memory."),
    user_id: str | None = typer.Option(
        None, "--user-id", "-u", help="Scope to user.", rich_help_panel="Scope"
    ),
    agent_id: str | None = typer.Option(
        None, "--agent-id", help="Scope to agent.", rich_help_panel="Scope"
    ),
    app_id: str | None = typer.Option(
        None, "--app-id", help="Scope to app.", rich_help_panel="Scope"
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Scope to run.", rich_help_panel="Scope"
    ),
    messages: str | None = typer.Option(None, "--messages", help="Conversation messages as JSON."),
    file: Path | None = typer.Option(None, "--file", "-f", help="Read messages from JSON file."),
    metadata: str | None = typer.Option(None, "--metadata", "-m", help="Custom metadata as JSON."),
    immutable: bool = typer.Option(False, "--immutable", help="Prevent future updates."),
    no_infer: bool = typer.Option(False, "--no-infer", help="Skip inference, store raw."),
    expires: str | None = typer.Option(None, "--expires", help="Expiration date (YYYY-MM-DD)."),
    categories: str | None = typer.Option(
        None, "--categories", help="Categories (JSON array or comma-separated)."
    ),
    output: str = typer.Option(
        "text", "--output", "-o", help="Output format: text, json, quiet.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Add a memory from text, messages, file, or stdin.

    Examples:
      mem0 add "I prefer dark mode" --user-id alice
      echo "text" | mem0 add -u alice
      mem0 add --file msgs.json -u alice -o json
    """
    from mem0_cli.commands.memory import cmd_add

    backend, config = _get_backend_and_config(api_key, base_url)
    ids = _resolve_ids(config, user_id=user_id, agent_id=agent_id, app_id=app_id, run_id=run_id)

    cmd_add(
        backend,
        text,
        **ids,
        messages=messages,
        file=file,
        metadata=metadata,
        immutable=immutable,
        no_infer=no_infer,
        expires=expires,
        categories=categories,
        output=output,
    )


# ── Memory: search ────────────────────────────────────────────────────────


@app.command(rich_help_panel="Memory")
def search(
    query: str | None = typer.Argument(None, help="Search query."),
    user_id: str | None = typer.Option(
        None, "--user-id", "-u", help="Filter by user.", rich_help_panel="Scope"
    ),
    agent_id: str | None = typer.Option(
        None, "--agent-id", help="Filter by agent.", rich_help_panel="Scope"
    ),
    app_id: str | None = typer.Option(
        None, "--app-id", help="Filter by app.", rich_help_panel="Scope"
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Filter by run.", rich_help_panel="Scope"
    ),
    top_k: int = typer.Option(
        10, "--top-k", "-k", "--limit", help="Number of results.", rich_help_panel="Search"
    ),
    threshold: float = typer.Option(
        0.3, "--threshold", help="Minimum similarity score.", rich_help_panel="Search"
    ),
    rerank: bool = typer.Option(
        False, "--rerank", help="Enable reranking (Platform only).", rich_help_panel="Search"
    ),
    keyword: bool = typer.Option(
        False, "--keyword", help="Use keyword search.", rich_help_panel="Search"
    ),
    filter_json: str | None = typer.Option(
        None, "--filter", help="Advanced filter expression (JSON).", rich_help_panel="Search"
    ),
    fields: str | None = typer.Option(
        None,
        "--fields",
        help="Specific fields to return (comma-separated).",
        rich_help_panel="Search",
    ),
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json, table.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Query your memory store — semantic, keyword, or hybrid retrieval.

    Examples:
      mem0 search "preferences" --user-id alice
      mem0 search "tools" -u alice -o json -k 5
      echo "preferences" | mem0 search -u alice
    """
    from mem0_cli.commands.memory import cmd_search

    # STEP 7: stdin fallback for query
    if query is None:
        query = _read_stdin()
    if not query or not query.strip():
        print_error(err_console, "Search query cannot be empty.")
        raise typer.Exit(1)

    backend, config = _get_backend_and_config(api_key, base_url)
    ids = _resolve_ids(config, user_id=user_id, agent_id=agent_id, app_id=app_id, run_id=run_id)

    cmd_search(
        backend,
        query,
        **ids,
        top_k=top_k,
        threshold=threshold,
        rerank=rerank,
        keyword=keyword,
        filter_json=filter_json,
        fields=fields,
        output=output,
    )


# ── Memory: get ───────────────────────────────────────────────────────────


@app.command(rich_help_panel="Memory")
def get(
    memory_id: str = typer.Argument(..., help="Memory ID to retrieve."),
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Get a specific memory by ID.

    Examples:
      mem0 get abc-123-def-456
      mem0 get abc-123-def-456 -o json
    """
    from mem0_cli.commands.memory import cmd_get

    backend = _get_backend(api_key, base_url)
    cmd_get(backend, memory_id, output=output)


# ── Memory: list ──────────────────────────────────────────────────────────


@app.command(name="list", rich_help_panel="Memory")
def list_cmd(
    user_id: str | None = typer.Option(
        None, "--user-id", "-u", help="Filter by user.", rich_help_panel="Scope"
    ),
    agent_id: str | None = typer.Option(
        None, "--agent-id", help="Filter by agent.", rich_help_panel="Scope"
    ),
    app_id: str | None = typer.Option(
        None, "--app-id", help="Filter by app.", rich_help_panel="Scope"
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Filter by run.", rich_help_panel="Scope"
    ),
    page: int = typer.Option(1, "--page", help="Page number.", rich_help_panel="Pagination"),
    page_size: int = typer.Option(
        100, "--page-size", help="Results per page.", rich_help_panel="Pagination"
    ),
    category: str | None = typer.Option(
        None, "--category", help="Filter by category.", rich_help_panel="Filters"
    ),
    after: str | None = typer.Option(
        None, "--after", help="Created after (YYYY-MM-DD).", rich_help_panel="Filters"
    ),
    before: str | None = typer.Option(
        None, "--before", help="Created before (YYYY-MM-DD).", rich_help_panel="Filters"
    ),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: text, json, table.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """List memories with optional filters.

    Examples:
      mem0 list -u alice
      mem0 list --category prefs --after 2024-01-01 -o json
    """
    from mem0_cli.commands.memory import cmd_list

    backend, config = _get_backend_and_config(api_key, base_url)
    ids = _resolve_ids(config, user_id=user_id, agent_id=agent_id, app_id=app_id, run_id=run_id)

    cmd_list(
        backend,
        **ids,
        page=page,
        page_size=page_size,
        category=category,
        after=after,
        before=before,
        output=output,
    )


# ── Memory: update ────────────────────────────────────────────────────────


@app.command(rich_help_panel="Memory")
def update(
    memory_id: str = typer.Argument(..., help="Memory ID to update."),
    text: str | None = typer.Argument(None, help="New memory text."),
    metadata: str | None = typer.Option(None, "--metadata", "-m", help="Update metadata (JSON)."),
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json, quiet.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Update a memory's text or metadata.

    Examples:
      mem0 update abc-123-def-456 "new text"
      mem0 update abc-123 --metadata '{{"key":"val"}}'
      echo "new text" | mem0 update abc-123
    """
    from mem0_cli.commands.memory import cmd_update

    # STEP 7: stdin fallback for text
    if text is None:
        text = _read_stdin()

    backend = _get_backend(api_key, base_url)
    cmd_update(backend, memory_id, text, metadata=metadata, output=output)


# ── Memory: delete ────────────────────────────────────────────────────────


@app.command(rich_help_panel="Memory")
def delete(
    memory_id: str | None = typer.Argument(
        None, help="Memory ID to delete (omit when using --all or --entity)."
    ),
    all_: bool = typer.Option(False, "--all", help="Delete all memories matching scope filters."),
    entity: bool = typer.Option(
        False, "--entity", help="Delete the entity itself and all its memories (cascade)."
    ),
    project: bool = typer.Option(
        False, "--project", help="With --all: delete ALL memories project-wide."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without deleting."
    ),
    force: bool = typer.Option(False, "--force", help="Skip confirmation."),
    user_id: str | None = typer.Option(
        None, "--user-id", "-u", help="Scope to user.", rich_help_panel="Scope"
    ),
    agent_id: str | None = typer.Option(
        None, "--agent-id", help="Scope to agent.", rich_help_panel="Scope"
    ),
    app_id: str | None = typer.Option(
        None, "--app-id", help="Scope to app.", rich_help_panel="Scope"
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Scope to run.", rich_help_panel="Scope"
    ),
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json, quiet.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Delete a memory, all memories, or an entity.

    Examples:
      mem0 delete abc-123-def-456
      mem0 delete abc-123 --dry-run
      mem0 delete --all -u alice --force
      mem0 delete --all --project --force
      mem0 delete --entity -u alice --force
    """
    # ── Validate mutual exclusion ────────────────────────────────────
    modes = sum([memory_id is not None, all_, entity])
    if modes > 1:
        print_error(
            err_console,
            "Only one of memory ID, --all, or --entity may be used at a time.",
        )
        raise typer.Exit(1)
    if modes == 0:
        print_error(
            err_console,
            "Provide a memory ID, --all, or --entity.",
            hint="Run 'mem0 delete --help' for usage.",
        )
        raise typer.Exit(1)

    # ── Dispatch ─────────────────────────────────────────────────────
    if memory_id is not None:
        _fire_telemetry("delete", {"delete_mode": "single"})
        from mem0_cli.commands.memory import cmd_delete

        backend = _get_backend(api_key, base_url)
        cmd_delete(backend, memory_id, dry_run=dry_run, force=force, output=output)

    elif all_:
        _fire_telemetry("delete", {"delete_mode": "all"})
        from mem0_cli.commands.memory import cmd_delete_all

        backend, config = _get_backend_and_config(api_key, base_url)
        ids = _resolve_ids(config, user_id=user_id, agent_id=agent_id, app_id=app_id, run_id=run_id)
        cmd_delete_all(backend, force=force, dry_run=dry_run, all_=project, **ids, output=output)

    else:  # --entity
        _fire_telemetry("delete", {"delete_mode": "entity"})
        from mem0_cli.commands.entities import cmd_entities_delete

        backend = _get_backend(api_key, base_url)
        cmd_entities_delete(
            backend,
            user_id=user_id,
            agent_id=agent_id,
            app_id=app_id,
            run_id=run_id,
            force=force,
            dry_run=dry_run,
            output=output,
        )


# ── Config subcommands ────────────────────────────────────────────────────


@config_app.command("show")
def config_show(
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json.", rich_help_panel="Output"
    ),
) -> None:
    """Display current configuration (secrets redacted).

    Examples:
      mem0 config show
      mem0 config show -o json
    """
    from mem0_cli.commands.config_cmd import cmd_config_show

    cmd_config_show(output=output)


@config_app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Config key (e.g. platform.api_key)."),
) -> None:
    """Get a configuration value.

    Examples:
      mem0 config get platform.api_key
      mem0 config get defaults.user_id
    """
    from mem0_cli.commands.config_cmd import cmd_config_get

    cmd_config_get(key)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key (e.g. platform.api_key)."),
    value: str = typer.Argument(..., help="Value to set."),
) -> None:
    """Set a configuration value.

    Examples:
      mem0 config set defaults.user_id alice
      mem0 config set platform.base_url https://custom.api.mem0.ai
    """
    from mem0_cli.commands.config_cmd import cmd_config_set

    cmd_config_set(key, value)


# ── Entity subcommands ────────────────────────────────────────────────────


@entity_app.command("list")
def entity_list(
    entity_type: str = typer.Argument(..., help="Entity type: users, agents, apps, runs."),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: table, json.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """List all entities of a given type.

    Examples:
      mem0 entity list users
      mem0 entity list agents -o json
    """
    from mem0_cli.commands.entities import cmd_entities_list

    backend = _get_backend(api_key, base_url)
    cmd_entities_list(backend, entity_type, output=output)


@entity_app.command("delete")
def entity_delete(
    user_id: str | None = typer.Option(
        None, "--user-id", "-u", help="User ID.", rich_help_panel="Scope"
    ),
    agent_id: str | None = typer.Option(
        None, "--agent-id", help="Agent ID.", rich_help_panel="Scope"
    ),
    app_id: str | None = typer.Option(None, "--app-id", help="App ID.", rich_help_panel="Scope"),
    run_id: str | None = typer.Option(None, "--run-id", help="Run ID.", rich_help_panel="Scope"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without deleting."
    ),
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json, quiet.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Delete an entity and ALL its memories (cascade).

    Examples:
      mem0 entity delete --user-id alice --force
      mem0 entity delete -u alice --dry-run
    """
    from mem0_cli.commands.entities import cmd_entities_delete

    backend = _get_backend(api_key, base_url)
    cmd_entities_delete(
        backend,
        user_id=user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id,
        force=force,
        dry_run=dry_run,
        output=output,
    )


# ── Entity subgroup ──
app.add_typer(entity_app, name="entity", rich_help_panel="Management")


# ── Event subcommands ─────────────────────────────────────────────────────


@event_app.command("list")
def event_list(
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: table, json.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """List recent background processing events.

    Examples:
      mem0 event list
      mem0 event list -o json
    """
    from mem0_cli.commands.events_cmd import cmd_event_list

    backend = _get_backend(api_key, base_url)
    cmd_event_list(backend, output=output)


@event_app.command("status")
def event_status(
    event_id: str = typer.Argument(..., help="Event ID to inspect."),
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Check the status of a specific background event.

    Examples:
      mem0 event status <event-id>
      mem0 event status <event-id> -o json
    """
    from mem0_cli.commands.events_cmd import cmd_event_status

    backend = _get_backend(api_key, base_url)
    cmd_event_status(backend, event_id, output=output)


# ── Event subgroup ──
app.add_typer(event_app, name="event", rich_help_panel="Management")


# ── Management commands ───────────────────────────────────────────────────


@app.command(rich_help_panel="Management")
def init(
    api_key: str | None = typer.Option(None, "--api-key", help="API key (skip prompt)."),
    user_id: str | None = typer.Option(
        None, "--user-id", "-u", help="Default user ID (skip prompt)."
    ),
    email: str | None = typer.Option(None, "--email", help="Login via email verification code."),
    code: str | None = typer.Option(
        None, "--code", help="Verification code (use with --email for non-interactive login)."
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing config without confirmation."
    ),
    agent_signal: bool = typer.Option(
        False, "--agent", help="Bootstrap an unattended Agent Mode account (no email required)."
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        help="Channel attribution for signup (e.g. github, hn, ph).",
    ),
    agent_caller: str | None = typer.Option(
        None,
        "--agent-caller",
        help="Self-declared agent identity (e.g. claude-code, cursor). Used with --agent to attribute Agent Mode signups.",
    ),
) -> None:
    """Interactive setup wizard for mem0 CLI.

    Examples:
      mem0 init
      mem0 init --api-key m0-xxx --user-id alice
      mem0 init --email alice@company.com
      mem0 init --email alice@company.com --code 482901
      mem0 init --agent --agent-caller claude-code   # AI agent self-identifies on Agent Mode bootstrap
      mem0 init --email alice@company.com  # Claims an existing Agent Mode key when one is present
    """
    from mem0_cli.commands.init_cmd import run_init

    run_init(
        api_key=api_key,
        user_id=user_id,
        email=email,
        code=code,
        force=force,
        source=source,
        agent=agent_signal,
        agent_caller=agent_caller,
    )


@app.command(rich_help_panel="Setup")
def identify(
    name: str = typer.Argument(..., help="Agent identity (e.g. claude-code, cursor, my-bot)."),
) -> None:
    """Tag your active Agent Mode key with the AI agent that's using it.

    Run this once after `mem0 init --agent` if you didn't pass --agent-caller.
    Idempotent — re-running just overwrites the value.

    Example:
      mem0 identify claude-code
    """
    from mem0_cli.commands.identify_cmd import run_identify

    run_identify(name)


# (entity_app registered at module level, below sub-group definitions)


@app.command(rich_help_panel="Management")
def status(
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Check connectivity and authentication.

    Examples:
      mem0 status
      mem0 status -o json
    """
    from mem0_cli.commands.utils import cmd_status

    backend, config = _get_backend_and_config(api_key, base_url)
    cmd_status(
        backend,
        user_id=config.defaults.user_id or None,
        agent_id=config.defaults.agent_id or None,
        output=output,
    )


@app.command("import", rich_help_panel="Management")
def import_cmd(
    file_path: str = typer.Argument(..., help="JSON file to import."),
    user_id: str | None = typer.Option(
        None, "--user-id", "-u", help="Override user ID.", rich_help_panel="Scope"
    ),
    agent_id: str | None = typer.Option(
        None, "--agent-id", help="Override agent ID.", rich_help_panel="Scope"
    ),
    output: str = typer.Option(
        "text", "--output", "-o", help="Output: text, json.", rich_help_panel="Output"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key.",
        envvar="MEM0_API_KEY",
        rich_help_panel="Connection",
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override API base URL.", rich_help_panel="Connection"
    ),
) -> None:
    """Import memories from a JSON file.

    Examples:
      mem0 import data.json --user-id alice
      mem0 import data.json -u alice -o json
    """
    from mem0_cli.commands.utils import cmd_import

    backend, config = _get_backend_and_config(api_key, base_url)
    ids = _resolve_ids(config, user_id=user_id, agent_id=agent_id)
    cmd_import(backend, file_path, user_id=ids["user_id"], agent_id=ids["agent_id"], output=output)


# ── Help (machine-readable) ──────────────────────────────────────────────


def _build_help_json() -> dict:
    """Build machine-readable JSON describing all CLI commands."""
    commands = {
        "add": {
            "description": "Add a memory from text, messages, file, or stdin.",
            "usage": "mem0 add <text> [OPTIONS]",
            "arguments": {
                "text": {"description": "Text content to add as a memory.", "required": False}
            },
            "options": {
                "--user-id, -u": "Scope to user.",
                "--agent-id": "Scope to agent.",
                "--app-id": "Scope to app.",
                "--run-id": "Scope to run.",
                "--messages": "Conversation messages as JSON.",
                "--file, -f": "Read messages from JSON file.",
                "--metadata, -m": "Custom metadata as JSON.",
                "--immutable": "Prevent future updates.",
                "--no-infer": "Skip inference, store raw.",
                "--expires": "Expiration date (YYYY-MM-DD).",
                "--categories": "Categories (JSON array or comma-separated).",
                "--graph": "Enable graph memory extraction.",
                "--no-graph": "Disable graph memory extraction.",
                "--output, -o": "Output format: text, json, quiet.",
            },
        },
        "search": {
            "description": "Query your memory store — semantic, keyword, or hybrid retrieval.",
            "usage": "mem0 search <query> [OPTIONS]",
            "arguments": {"query": {"description": "Search query.", "required": False}},
            "options": {
                "--user-id, -u": "Filter by user.",
                "--agent-id": "Filter by agent.",
                "--top-k, -k, --limit": "Number of results (default: 10).",
                "--threshold": "Minimum similarity score (default: 0.3).",
                "--rerank": "Enable reranking (Platform only).",
                "--keyword": "Use keyword search instead of semantic.",
                "--filter": "Advanced filter expression (JSON).",
                "--fields": "Specific fields to return (comma-separated).",
                "--graph": "Enable graph in search.",
                "--no-graph": "Disable graph in search.",
                "--output, -o": "Output format: text, json, table.",
            },
        },
        "get": {
            "description": "Get a specific memory by ID.",
            "usage": "mem0 get <memory_id> [OPTIONS]",
            "arguments": {"memory_id": {"description": "Memory ID to retrieve.", "required": True}},
            "options": {"--output, -o": "Output format: text, json."},
        },
        "list": {
            "description": "List memories with optional filters.",
            "usage": "mem0 list [OPTIONS]",
            "arguments": {},
            "options": {
                "--user-id, -u": "Filter by user.",
                "--agent-id": "Filter by agent.",
                "--page": "Page number (default: 1).",
                "--page-size": "Results per page (default: 100).",
                "--category": "Filter by category.",
                "--after": "Created after (YYYY-MM-DD).",
                "--before": "Created before (YYYY-MM-DD).",
                "--graph": "Enable graph in listing.",
                "--no-graph": "Disable graph in listing.",
                "--output, -o": "Output format: text, json, table.",
            },
        },
        "update": {
            "description": "Update a memory's text or metadata.",
            "usage": "mem0 update <memory_id> [text] [OPTIONS]",
            "arguments": {
                "memory_id": {"description": "Memory ID to update.", "required": True},
                "text": {"description": "New memory text.", "required": False},
            },
            "options": {
                "--metadata, -m": "Update metadata (JSON).",
                "--output, -o": "Output format: text, json, quiet.",
            },
        },
        "delete": {
            "description": "Delete a memory, all memories, or an entity.",
            "usage": "mem0 delete [memory_id] [OPTIONS]",
            "arguments": {
                "memory_id": {
                    "description": "Memory ID to delete (omit when using --all or --entity).",
                    "required": False,
                }
            },
            "options": {
                "--all": "Delete all memories matching scope filters.",
                "--entity": "Delete the entity itself and all its memories (cascade).",
                "--project": "With --all: delete ALL memories project-wide.",
                "--dry-run": "Show what would be deleted without deleting.",
                "--force": "Skip confirmation.",
                "--user-id, -u": "Scope to user.",
                "--agent-id": "Scope to agent.",
                "--app-id": "Scope to app.",
                "--run-id": "Scope to run.",
                "--output, -o": "Output format: text, json, quiet.",
            },
        },
        "import": {
            "description": "Import memories from a JSON file.",
            "usage": "mem0 import <file_path> [OPTIONS]",
            "arguments": {"file_path": {"description": "JSON file to import.", "required": True}},
            "options": {
                "--user-id, -u": "Override user ID.",
                "--agent-id": "Override agent ID.",
                "--output, -o": "Output format: text, json.",
            },
        },
        "config show": {
            "description": "Display current configuration (secrets redacted).",
            "usage": "mem0 config show",
            "options": {"--output, -o": "Output format: text, json."},
        },
        "config get": {
            "description": "Get a configuration value.",
            "usage": "mem0 config get <key>",
            "arguments": {
                "key": {"description": "Config key (e.g. platform.api_key).", "required": True}
            },
        },
        "config set": {
            "description": "Set a configuration value.",
            "usage": "mem0 config set <key> <value>",
            "arguments": {
                "key": {"description": "Config key (e.g. platform.api_key).", "required": True},
                "value": {"description": "Value to set.", "required": True},
            },
        },
        "event": {
            "description": "Inspect background processing events.",
            "subcommands": {
                "list": {
                    "description": "List recent background processing events.",
                    "usage": "mem0 event list [OPTIONS]",
                    "options": {"--output, -o": "Output format: table, json."},
                },
                "status": {
                    "description": "Check the status of a specific background event.",
                    "usage": "mem0 event status <event_id> [OPTIONS]",
                    "arguments": {
                        "event_id": {"description": "Event ID to inspect.", "required": True}
                    },
                    "options": {"--output, -o": "Output format: text, json."},
                },
            },
        },
        "entity": {
            "description": "Manage entities.",
            "subcommands": {
                "list": {
                    "description": "List all entities of a given type.",
                    "usage": "mem0 entity list <entity_type> [OPTIONS]",
                    "arguments": {
                        "entity_type": {
                            "description": "Entity type: users, agents, apps, runs.",
                            "required": True,
                        }
                    },
                    "options": {"--output, -o": "Output format: table, json."},
                },
                "delete": {
                    "description": "Delete an entity and ALL its memories (cascade).",
                    "usage": "mem0 entity delete [OPTIONS]",
                    "options": {
                        "--user-id, -u": "User ID.",
                        "--agent-id": "Agent ID.",
                        "--app-id": "App ID.",
                        "--run-id": "Run ID.",
                        "--force": "Skip confirmation.",
                        "--dry-run": "Show what would be deleted without deleting.",
                        "--output, -o": "Output format: text, json, quiet.",
                    },
                },
            },
        },
        "init": {
            "description": "Interactive setup wizard for mem0 CLI.",
            "usage": "mem0 init",
            "options": {
                "--api-key": "API key (skip prompt).",
                "--user-id, -u": "Default user ID (skip prompt).",
            },
        },
        "status": {
            "description": "Check connectivity and authentication.",
            "usage": "mem0 status [OPTIONS]",
            "options": {"--output, -o": "Output format: text, json."},
        },
    }
    return {
        "name": "mem0",
        "version": __version__,
        "description": "The Memory Layer for AI Agents",
        "commands": commands,
        "global_options": {
            "--api-key": "Override API key (env: MEM0_API_KEY).",
            "--base-url": "Override API base URL.",
            "--json / --agent": "Output as JSON for agent/programmatic use.",
            "--help": "Show help for a command.",
            "--version": "Show version and exit.",
        },
        "help": {
            "human": "mem0 <command> --help    Get help for a command",
            "machine": "mem0 help --json         Machine-readable help (for LLM agents)",
        },
    }


@app.command(rich_help_panel="Management")
def help(
    json: bool = typer.Option(False, "--json", help="Output machine-readable JSON for LLM agents."),
) -> None:
    """Show help. Use --json for machine-readable output (for LLM agents).

    Examples:
      mem0 help
      mem0 help --json
    """
    if json:
        console.print(_json.dumps(_build_help_json(), indent=2))
    else:
        console.print(
            f"[{BRAND_COLOR}]◆ mem0 CLI[/] v{__version__} — The Memory Layer for AI Agents\n"
        )
        console.print("Usage: mem0 <command> [OPTIONS]\n")
        console.print("[bold]Commands:[/]")
        console.print("  add              Add a memory from text, messages, file, or stdin")
        console.print("  search           Query your memory store (semantic, keyword, hybrid)")
        console.print("  get              Get a specific memory by ID")
        console.print("  list             List memories with optional filters")
        console.print("  update           Update a memory's text or metadata")
        console.print("  delete           Delete a memory, all memories, or an entity")
        console.print("  import           Import memories from a JSON file")
        console.print("  config           Manage configuration (show, get, set)")
        console.print("  entity           Manage entities (list, delete)")
        console.print("  event            Inspect background events (list, status)")
        console.print("  init             Interactive setup wizard")
        console.print("  status           Check connectivity and authentication")
        console.print()
        console.print("  mem0 <command> --help    Get help for a command")
        console.print("  mem0 help --json         Machine-readable help (for LLM agents)")
        console.print()


# Register config subgroup here so it appears after help in Management panel
app.add_typer(config_app, name="config", rich_help_panel="Management")


# ── Entrypoint ────────────────────────────────────────────────────────────


def main() -> None:
    import sys

    # Allow --json/--agent anywhere in the command line (not just before subcommand).
    # Special case: `mem0 init --agent` is a subcommand flag (Agent Mode bootstrap)
    # consumed by init_cmd, not a global JSON-output toggle — leave it in argv.
    argv_rest = sys.argv[1:]
    is_init = "init" in argv_rest
    _global_flags = {"--json"} if is_init else {"--json", "--agent"}
    if any(a in _global_flags for a in argv_rest):
        from mem0_cli.state import set_agent_mode

        set_agent_mode(True)
        sys.argv = [sys.argv[0]] + [a for a in argv_rest if a not in _global_flags]

    try:
        app()
    finally:
        # Surface any unclaimed Agent Mode notice once per command, after the
        # primary output. In JSON/agent mode the notice is folded into the
        # envelope by format_json_envelope, so skip the stderr banner there
        # to avoid duplicate output.
        from mem0_cli.state import is_agent_mode, take_notice

        notice = take_notice()
        if notice and not is_agent_mode():
            from rich.console import Console

            Console(stderr=True).print(f"\n[yellow]🔔 {notice}[/yellow]\n")
