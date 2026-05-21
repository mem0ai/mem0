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


def load_retention_policies(cwd: str | None = None) -> dict[str, int | None]:
    """Load retention policies from the mem0.md in *cwd*.

    Combines :func:`find_mem0_config` and :func:`parse_retention` into a
    single convenience function.

    Args:
        cwd: Directory to search.  Defaults to ``os.getcwd()``.

    Returns:
        Retention dict (category → days or ``None``).  Empty dict if no
        ``mem0.md`` exists in *cwd* or it contains no ``## Retention``
        section.
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

    Reads cwd from ``sys.argv[1]`` (or ``os.getcwd()``), prints JSON to
    stdout.
    """
    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    policies = load_retention_policies(cwd)
    print(json.dumps(policies))
    return 0


if __name__ == "__main__":
    sys.exit(main())
