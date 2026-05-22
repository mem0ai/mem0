#!/usr/bin/env python3
"""Import memories from competing AI tool configuration files into mem0.

Sub-commands (via sys.argv[1]):
  cursorrules [--path .cursorrules]
  copilot     [--path .github/copilot-instructions.md]
  cline       [--path memory-bank/]
  continue    [--path .continue/rules.md]

Each sub-command reads configuration files from competing tools,
splits them into chunks, and POSTs each chunk to the mem0 API as a
project_profile memory.

Output: progress messages to stdout, errors to stderr
Exit:   0 always
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _chunking import (
    filter_and_truncate,
    split_by_headers,
    split_by_hr_or_headers,
)
from _identity import resolve_api_key, resolve_user_id
from _project import resolve_branch, resolve_project_id

API_URL = "https://api.mem0.ai"

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def post_memory(api_key: str, content: str, user_id: str, project_id: str, branch: str, source: str) -> bool:
    """POST a single memory chunk to the mem0 API."""
    metadata: dict = {
        "type": "project_profile",
        "source": source,
    }
    if branch:
        metadata["branch"] = branch

    body = {
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
        "app_id": project_id,
        "metadata": metadata,
        "infer": False,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/v3/memories/add/",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Token {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status in (200, 201)
    except urllib.error.URLError as e:
        print(f"  [warn] API call failed: {e}", file=sys.stderr)
        return False


def import_chunks(chunks: list[str], api_key: str, user_id: str, project_id: str, branch: str, source: str) -> int:
    """Import a list of content chunks; return number of successful imports."""
    success = 0
    for chunk in chunks:
        if post_memory(api_key, chunk, user_id, project_id, branch, source):
            success += 1
    return success


# ---------------------------------------------------------------------------
# Sub-command implementations
# ---------------------------------------------------------------------------


def _parse_path_arg(args: list[str], flag: str, default: str) -> str:
    """Extract --path <value> from args list, falling back to default."""
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(f"{flag}="):
            return arg[len(flag) + 1:]
    return default


def cmd_cursorrules(args: list[str]) -> None:
    path = _parse_path_arg(args, "--path", ".cursorrules")
    source = "cursor-import"

    api_key = resolve_api_key()
    user_id = resolve_user_id()
    project_id = resolve_project_id()
    branch = resolve_branch()

    if not api_key:
        print("Error: MEM0_API_KEY not set", file=sys.stderr)
        return

    if not os.path.isfile(path):
        print(f"File not found: {path}", file=sys.stderr)
        return

    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    raw_chunks = split_by_headers(content, "## ")
    # Fall back to treating the whole file as one chunk if no headers found
    if not raw_chunks:
        raw_chunks = [content.strip()] if content.strip() else []

    chunks = filter_and_truncate(raw_chunks)
    n = import_chunks(chunks, api_key, user_id, project_id, branch, source)
    print(f"Imported {n} memories from {source} ({path})")


def cmd_copilot(args: list[str]) -> None:
    path = _parse_path_arg(args, "--path", ".github/copilot-instructions.md")
    source = "copilot-import"

    api_key = resolve_api_key()
    user_id = resolve_user_id()
    project_id = resolve_project_id()
    branch = resolve_branch()

    if not api_key:
        print("Error: MEM0_API_KEY not set", file=sys.stderr)
        return

    if not os.path.isfile(path):
        print(f"File not found: {path}", file=sys.stderr)
        return

    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    raw_chunks = split_by_headers(content, "## ")
    if not raw_chunks:
        raw_chunks = [content.strip()] if content.strip() else []

    chunks = filter_and_truncate(raw_chunks)
    n = import_chunks(chunks, api_key, user_id, project_id, branch, source)
    print(f"Imported {n} memories from {source} ({path})")


def cmd_cline(args: list[str]) -> None:
    dir_path = _parse_path_arg(args, "--path", "memory-bank/")
    source = "cline-import"

    api_key = resolve_api_key()
    user_id = resolve_user_id()
    project_id = resolve_project_id()
    branch = resolve_branch()

    if not api_key:
        print("Error: MEM0_API_KEY not set", file=sys.stderr)
        return

    if not os.path.isdir(dir_path):
        print(f"Directory not found: {dir_path}", file=sys.stderr)
        return

    md_files = sorted(
        f for f in os.listdir(dir_path) if f.endswith(".md")
    )
    if not md_files:
        print(f"No .md files found in {dir_path}", file=sys.stderr)
        return

    total = 0
    for filename in md_files:
        filepath = os.path.join(dir_path, filename)
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read().strip()
        if not content:
            continue
        chunks = filter_and_truncate([content])
        n = import_chunks(chunks, api_key, user_id, project_id, branch, source)
        total += n

    print(f"Imported {total} memories from {source} ({dir_path})")


def cmd_continue(args: list[str]) -> None:
    path = _parse_path_arg(args, "--path", ".continue/rules.md")
    source = "continue-import"

    api_key = resolve_api_key()
    user_id = resolve_user_id()
    project_id = resolve_project_id()
    branch = resolve_branch()

    if not api_key:
        print("Error: MEM0_API_KEY not set", file=sys.stderr)
        return

    if not os.path.isfile(path):
        print(f"File not found: {path}", file=sys.stderr)
        return

    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    raw_chunks = split_by_hr_or_headers(content)
    if not raw_chunks:
        raw_chunks = [content.strip()] if content.strip() else []

    chunks = filter_and_truncate(raw_chunks)
    n = import_chunks(chunks, api_key, user_id, project_id, branch, source)
    print(f"Imported {n} memories from {source} ({path})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMANDS = {
    "cursorrules": cmd_cursorrules,
    "copilot": cmd_copilot,
    "cline": cmd_cline,
    "continue": cmd_continue,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        available = ", ".join(COMMANDS.keys())
        print("Usage: import_competing_tools.py <subcommand> [--path <path>]", file=sys.stderr)
        print(f"Subcommands: {available}", file=sys.stderr)
        sys.exit(0)

    subcommand = sys.argv[1]
    remaining_args = sys.argv[2:]
    COMMANDS[subcommand](remaining_args)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
    sys.exit(0)
