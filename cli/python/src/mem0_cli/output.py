"""Output formatting for mem0 CLI — text, JSON, table, quiet modes."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mem0_cli.branding import ACCENT_COLOR, BRAND_COLOR, DIM_COLOR, SUCCESS_COLOR, _sym


def format_memories_text(console: Console, memories: list[dict], title: str = "memories") -> None:
    """Render memories in human-friendly text mode."""
    count = len(memories)
    console.print(f"\n[{BRAND_COLOR}]Found {count} {title}:[/]\n")

    for i, mem in enumerate(memories, 1):
        memory_text = mem.get("memory", mem.get("text", ""))
        mem_id = mem.get("id", "")[:8]
        score = mem.get("score")
        created = _format_date(mem.get("created_at"))
        category = mem.get("categories", [None])
        if isinstance(category, list):
            category = category[0] if category else None

        line = Text()
        line.append(f"  {i}. ", style="bold")
        line.append(memory_text, style="white")
        console.print(line)

        details = []
        if score is not None:
            details.append(f"Score: {score:.2f}")
        if mem_id:
            details.append(f"ID: {mem_id}")
        if created:
            details.append(f"Created: {created}")
        if category:
            details.append(f"Category: {category}")

        if details:
            detail_str = " · ".join(details)
            console.print(f"     [{DIM_COLOR}]{detail_str}[/]")
        console.print()


def format_memories_table(
    console: Console, memories: list[dict], *, show_score: bool = False
) -> None:
    """Render memories in a rich table."""
    table = Table(
        border_style=BRAND_COLOR,
        header_style=f"bold {ACCENT_COLOR}",
        row_styles=["", "dim"],
        padding=(0, 1),
    )
    table.add_column("ID", style="dim", max_width=38, no_wrap=True)
    if show_score:
        table.add_column("Score", max_width=7, justify="right")
    table.add_column("Memory", max_width=50, no_wrap=False)
    table.add_column("Category", max_width=14)
    table.add_column("Created", max_width=12)

    for mem in memories:
        mem_id = mem.get("id", "")
        memory_text = mem.get("memory", mem.get("text", ""))
        if len(memory_text) > 60:
            memory_text = memory_text[:57] + "..."
        categories = mem.get("categories", [])
        if isinstance(categories, list) and categories:
            cat = (
                categories[0]
                if len(categories) == 1
                else f"{categories[0]} (+{len(categories) - 1})"
            )
        else:
            cat = "—"
        created = _format_date(mem.get("created_at")) or "—"
        if show_score:
            score = mem.get("score")
            score_str = f"{score:.2f}" if score is not None else "—"
            table.add_row(mem_id, score_str, memory_text, cat, created)
        else:
            table.add_row(mem_id, memory_text, cat, created)

    console.print()
    console.print(table)
    console.print()


def format_json(console: Console, data: Any) -> None:
    """Output data as pretty-printed JSON."""
    console.print_json(json.dumps(data, default=str))


def format_single_memory(console: Console, mem: dict, output: str = "text") -> None:
    """Format a single memory for display."""
    if output == "json":
        format_json(console, mem)
        return

    memory_text = mem.get("memory", mem.get("text", ""))
    mem_id = mem.get("id", "")

    lines = []
    lines.append(f"  [white bold]{memory_text}[/]")
    lines.append("")

    if mem_id:
        lines.append(f"  [{DIM_COLOR}]ID:[/]         {mem_id}")
    created = _format_date(mem.get("created_at"))
    if created:
        lines.append(f"  [{DIM_COLOR}]Created:[/]    {created}")
    updated = _format_date(mem.get("updated_at"))
    if updated:
        lines.append(f"  [{DIM_COLOR}]Updated:[/]    {updated}")
    meta = mem.get("metadata")
    if meta:
        lines.append(f"  [{DIM_COLOR}]Metadata:[/]   {json.dumps(meta)}")
    categories = mem.get("categories")
    if categories:
        cat_str = ", ".join(categories) if isinstance(categories, list) else categories
        lines.append(f"  [{DIM_COLOR}]Categories:[/] {cat_str}")

    content = "\n".join(lines)
    panel = Panel(
        content,
        title=f"[{BRAND_COLOR}]Memory[/]",
        title_align="left",
        border_style=BRAND_COLOR,
        padding=(1, 1),
    )
    console.print()
    console.print(panel)
    console.print()


def format_add_result(console: Console, result: dict | list, output: str = "text") -> None:
    """Format the result of an add operation."""
    if output == "json":
        format_json(console, result)
        return
    if output == "quiet":
        return

    # result from API is typically {"results": [...]}
    results = result if isinstance(result, list) else result.get("results", [result])
    if not results:
        console.print(f"  [{DIM_COLOR}]No memories extracted.[/]")
        return

    console.print()
    seen_pending_events: set[str] = set()
    for r in results:
        # Detect async PENDING response from Platform API
        if r.get("status") == "PENDING":
            event_id = r.get("event_id", "")
            # Deduplicate PENDING entries with the same event_id
            if event_id and event_id in seen_pending_events:
                continue
            if event_id:
                seen_pending_events.add(event_id)
            icon = f"[{ACCENT_COLOR}]{_sym('⧗', '...')}[/]"
            parts = [f"  {icon} [{DIM_COLOR}]{'Queued':<10}[/]"]
            parts.append("[white]Processing in background[/]")
            console.print("  ".join(parts))
            if event_id:
                console.print(f"  [{DIM_COLOR}]  event_id: {event_id}[/]")
                console.print(f"  [{DIM_COLOR}]  → Check status: mem0 event status {event_id}[/]")
            continue

        event = r.get("event", "ADD")
        memory = r.get("memory") or r.get("text") or r.get("content") or r.get("data") or ""
        mem_id = (r.get("id") or r.get("memory_id") or "")[:8]

        if event == "ADD":
            icon = f"[{SUCCESS_COLOR}]+[/]"
            label = "Added"
        elif event == "UPDATE":
            icon = f"[{ACCENT_COLOR}]~[/]"
            label = "Updated"
        elif event == "DELETE":
            icon = "[red]-[/]"
            label = "Deleted"
        elif event == "NOOP":
            icon = f"[{DIM_COLOR}]·[/]"
            label = "No change"
        else:
            icon = f"[{DIM_COLOR}]?[/]"
            label = event

        # Build the display line
        parts = [f"  {icon} [{DIM_COLOR}]{label:<10}[/]"]
        if memory:
            parts.append(f"[white]{memory}[/]")
        if mem_id:
            parts.append(f"[{DIM_COLOR}]({mem_id})[/]")
        console.print("  ".join(parts))
    console.print()


def format_json_envelope(
    console: Console,
    *,
    command: str,
    data: Any,
    duration_ms: int | None = None,
    scope: dict | None = None,
    count: int | None = None,
    status: str = "success",
    error: str | None = None,
) -> None:
    """Output structured JSON envelope for AI agent consumption."""
    envelope: dict[str, Any] = {
        "status": status,
        "command": command,
    }
    if duration_ms is not None:
        envelope["duration_ms"] = duration_ms
    if scope is not None:
        envelope["scope"] = scope
    if count is not None:
        envelope["count"] = count
    if error:
        envelope["error"] = error
    envelope["data"] = data

    # If the platform flagged this as an unclaimed Agent Mode account, surface
    # the notice inside the JSON envelope so an agent consuming the output
    # sees it without needing to inspect HTTP headers.
    from mem0_cli.state import take_notice

    notice = take_notice()
    if notice:
        envelope["mem0_notice"] = notice

    console.print_json(json.dumps(envelope, default=str))


def sanitize_agent_data(command: str, data: Any) -> Any:
    """Project API response data to minimal relevant fields for agent consumption."""

    def pick(obj: dict, keys: list) -> dict:
        return {k: obj[k] for k in keys if k in obj}

    if data is None:
        return data

    if command == "add":
        items = data if isinstance(data, list) else [data]
        result = []
        for item in items:
            if item.get("status") == "PENDING":
                result.append(pick(item, ["status", "event_id"]))
            else:
                result.append(pick(item, ["id", "memory", "event"]))
        return result

    if command == "search":
        return [pick(r, ["id", "memory", "score", "created_at", "categories"]) for r in data]

    if command == "list":
        return [pick(r, ["id", "memory", "created_at", "categories"]) for r in data]

    if command == "get":
        return pick(data, ["id", "memory", "created_at", "updated_at", "categories", "metadata"])

    if command == "update":
        return pick(data, ["id", "memory"])

    if command in ("delete", "delete-all", "entity delete"):
        return data

    if command == "entity list":
        result = []
        for r in data:
            item = pick(r, ["type", "count"])
            item["name"] = r.get("name") or r.get("id", "")
            result.append(item)
        return result

    if command == "event list":
        return [pick(r, ["id", "event_type", "status", "latency", "created_at"]) for r in data]

    if command == "event status":
        ev = data
        raw_results = ev.get("results") or []
        sanitized_results = []
        for r in raw_results:
            nested = r.get("data") or {}
            memory = nested.get("memory") if isinstance(nested, dict) else None
            sanitized_results.append(
                {
                    "id": r.get("id"),
                    "event": r.get("event"),
                    "user_id": r.get("user_id"),
                    "memory": memory,
                }
            )
        result = pick(ev, ["id", "event_type", "status", "latency", "created_at", "updated_at"])
        result["results"] = sanitized_results
        return result

    # Pass-through: status, import, config show/get/set
    return data


def format_agent_envelope(
    console: Console,
    *,
    command: str,
    data: Any,
    duration_ms: int | None = None,
    scope: dict | None = None,
    count: int | None = None,
) -> None:
    """Output structured JSON envelope for agent/programmatic use (--json/--agent mode)."""
    envelope: dict[str, Any] = {
        "status": "success",
        "command": command,
    }
    if duration_ms is not None:
        envelope["duration_ms"] = duration_ms
    if scope:
        filtered = {k: v for k, v in scope.items() if v}
        if filtered:
            envelope["scope"] = filtered
    if count is not None:
        envelope["count"] = count
    envelope["data"] = sanitize_agent_data(command, data)

    # Surface the unclaimed-Agent-Mode notice (if any) in the envelope so an
    # agent reading the JSON output sees it without inspecting HTTP headers.
    from mem0_cli.state import take_notice

    notice = take_notice()
    if notice:
        envelope["mem0_notice"] = notice

    console.print_json(json.dumps(envelope, default=str))


def print_result_summary(
    console: Console,
    count: int,
    *,
    duration_secs: float | None = None,
    page: int | None = None,
    **scope_ids: str | None,
) -> None:
    """Print a summary footer after result lists."""
    parts = [f"{count} result{'s' if count != 1 else ''}"]
    if page is not None:
        parts.append(f"page {page}")
    scope_parts = [f"{k}={v}" for k, v in scope_ids.items() if v]
    if scope_parts:
        parts.append(", ".join(scope_parts))
    if duration_secs is not None:
        parts.append(f"{duration_secs:.2f}s")

    summary = " · ".join(parts)
    console.print(f"  [{DIM_COLOR}]{summary}[/]")
    console.print()


def _format_date(dt_str: str | None) -> str | None:
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return str(dt_str)[:10] if dt_str else None
