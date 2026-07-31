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

import hashlib
import json
import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api import add_memory
from _chunking import (
    filter_and_truncate,
    split_by_headers,
    split_by_hr_or_headers,
)
from _identity import resolve_api_key, resolve_user_id
from _project import resolve_branch, resolve_project_id

HASH_STORE = os.path.expanduser("~/.mem0/import_hashes.json")


def _load_hashes() -> dict[str, str]:
    if not os.path.isfile(HASH_STORE):
        return {}
    try:
        with open(HASH_STORE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_hashes(hashes: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(HASH_STORE), exist_ok=True)
    try:
        with open(HASH_STORE, "w") as f:
            json.dump(hashes, f, indent=2)
    except OSError:
        pass


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


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
    try:
        status, _result = add_memory(api_key, body, timeout=20)
        return status in (200, 201)
    except urllib.error.URLError as e:
        print(f"  [warn] API call failed: {e}", file=sys.stderr)
        return False


def import_chunks(chunks: list[str], api_key: str, user_id: str, project_id: str, branch: str, source: str, hash_key: str = "") -> int:
    """Import a list of content chunks; return number of successful imports.

    Skips import if content hash matches a previous run for the same hash_key."""
    if hash_key:
        combined = "\n".join(chunks)
        current_hash = _content_hash(combined)
        hashes = _load_hashes()
        if hashes.get(hash_key) == current_hash:
            print(f"Already imported (unchanged) -- skipping: {hash_key}")
            return 0
    else:
        current_hash = ""
        hashes = {}

    success = 0
    for chunk in chunks:
        if post_memory(api_key, chunk, user_id, project_id, branch, source):
            success += 1

    if success > 0 and hash_key and current_hash:
        hashes[hash_key] = current_hash
        _save_hashes(hashes)

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
    n = import_chunks(chunks, api_key, user_id, project_id, branch, source, hash_key=f"{project_id}:{source}:{path}")
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
    n = import_chunks(chunks, api_key, user_id, project_id, branch, source, hash_key=f"{project_id}:{source}:{path}")
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
        n = import_chunks(chunks, api_key, user_id, project_id, branch, source, hash_key=f"{project_id}:{source}:{filepath}")
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
    n = import_chunks(chunks, api_key, user_id, project_id, branch, source, hash_key=f"{project_id}:{source}:{path}")
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
