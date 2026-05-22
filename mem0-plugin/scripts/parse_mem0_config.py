#!/usr/bin/env python3
"""Parse mem0.md project configuration file.

Reads the optional ``mem0.md`` file in a project directory and extracts
retention policies from a ``## Retention`` section.

Retention format (inside the section):
  <category>: <N>d        — keep for N days
  <category>: forever     — never prune (returned as None)

Usage (CLI):
  python3 parse_mem0_config.py [<cwd>]

Prints a JSON object mapping category names to day counts (int) or null
(forever) on stdout.  Prints ``{}`` when no mem0.md or no ## Retention
section is found.
"""

from __future__ import annotations

import json
import os
import re
import sys


def find_mem0_config(cwd: str) -> str | None:
    """Look for ``mem0.md`` in *cwd*.

    Returns the absolute path to ``mem0.md`` if found, else ``None``.
    """
    candidate = os.path.join(cwd, "mem0.md")
    return candidate if os.path.isfile(candidate) else None


def parse_retention(content: str) -> dict[str, int | None]:
    """Parse the ``## Retention`` section of *content*.

    Scans for a heading that matches ``## Retention`` (case-insensitive),
    then reads lines until the next ``##``-level heading or end of string.

    Each non-blank, non-comment line inside the section is expected to be::

        <category>: <N>d     → days=N  (int)
        <category>: forever  → days=None

    Malformed lines are silently skipped.

    Args:
        content: Full text of a mem0.md file.

    Returns:
        Dict mapping category name (str) to day count (int) or ``None``
        (forever).  Empty dict when no ``## Retention`` section is found.
    """
    # Find the ## Retention section (allow any amount of trailing whitespace /
    # extra words, but the heading must start with "## Retention").
    section_match = re.search(
        r"^##\s+Retention[^\n]*\n(.*?)(?=^##\s|\Z)",
        content,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return {}

    section_text = section_match.group(1)
    policies: dict[str, int | None] = {}

    for line in section_text.splitlines():
        # Strip comments and whitespace
        line = re.sub(r"#.*$", "", line).strip()
        if not line:
            continue

        # Match "<category>: <value>"
        line_match = re.match(r"^([^:]+):\s*(.+)$", line)
        if not line_match:
            continue

        category = line_match.group(1).strip()
        value = line_match.group(2).strip().lower()

        if value == "forever":
            policies[category] = None
        else:
            days_match = re.match(r"^(\d+)d$", value)
            if days_match:
                policies[category] = int(days_match.group(1))
            # else: malformed value — skip silently

    return policies


def parse_section_kv(content: str, heading: str) -> dict[str, str]:
    """Parse a key-value section from mem0.md.

    Looks for ``## <heading>`` (case-insensitive) and reads ``key: value``
    lines until the next ``##``-level heading or end of string.
    """
    pattern = rf"^##\s+{re.escape(heading)}[^\n]*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not match:
        return {}

    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = re.sub(r"#.*$", "", line).strip()
        if not line:
            continue
        m = re.match(r"^([^:]+):\s*(.+)$", line)
        if m:
            result[m.group(1).strip()] = m.group(2).strip()
    return result


def parse_section_list(content: str, heading: str) -> list[str]:
    """Parse a list section from mem0.md.

    Looks for ``## <heading>`` and reads ``- item`` or bare lines.
    """
    pattern = rf"^##\s+{re.escape(heading)}[^\n]*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    items: list[str] = []
    for line in match.group(1).splitlines():
        line = re.sub(r"#.*$", "", line).strip()
        line = re.sub(r"^[-*]\s+", "", line).strip()
        if line:
            items.append(line)
    return items


def parse_ignore_patterns(content: str) -> list[str]:
    """Parse the ``## Ignore`` section of *content*.

    Each non-blank line is a glob pattern (e.g., ``node_modules``, ``*.lock``).
    Lines starting with ``#`` are comments and skipped.
    """
    pattern = r"^##\s+Ignore[^\n]*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    patterns: list[str] = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[-*]\s+", "", line).strip()
        if line:
            patterns.append(line)
    return patterns


def load_full_config(cwd: str | None = None) -> dict:
    """Load all config sections from mem0.md.

    Returns a dict with keys: retention, search, categories, identity,
    ignore, project_id.
    Each is populated only if the corresponding ``##`` section exists.
    """
    if cwd is None:
        cwd = os.getcwd()

    config_path = find_mem0_config(cwd)
    if config_path is None:
        return {}

    try:
        with open(config_path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return {}

    config: dict = {}

    retention = parse_retention(content)
    if retention:
        config["retention"] = retention

    search = parse_section_kv(content, "Search")
    if search:
        config["search"] = search

    categories = parse_section_list(content, "Categories")
    if categories:
        config["categories"] = categories
        config["default_categories"] = categories

    identity = parse_section_kv(content, "Identity")
    if identity:
        config["identity"] = identity
        if "project_id" in identity:
            config["project_id"] = identity["project_id"]

    ignore = parse_ignore_patterns(content)
    if ignore:
        config["ignore"] = ignore

    return config


def load_retention_policies(cwd: str | None = None) -> dict[str, int | None]:
    """Load retention policies from the mem0.md in *cwd*.

    Combines :func:`find_mem0_config` and :func:`parse_retention` into a
    single convenience function.
    """
    if cwd is None:
        cwd = os.getcwd()

    config_path = find_mem0_config(cwd)
    if config_path is None:
        return {}

    try:
        with open(config_path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return {}

    return parse_retention(content)


def main() -> int:
    """CLI entry point.

    With ``--full``, prints the complete config. Without it, prints only
    retention policies (backward-compatible).
    """
    full_mode = "--full" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cwd = args[0] if args else os.getcwd()

    if full_mode:
        config = load_full_config(cwd)
    else:
        config = load_retention_policies(cwd)
    print(json.dumps(config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
