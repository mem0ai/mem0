#!/usr/bin/env python3
"""Parse a mem0 export file and output JSON.

Input:  path to a mem0-export-*.md file (sys.argv[1])
Output: JSON array of memory records to stdout
Exit:   0 always

Each block in the file is delimited by lines containing exactly "---".
Blocks have a YAML-like frontmatter section (key: value lines) followed
by a blank line and the memory content text.

Example block format:
---
id: abc123
created_at: 2024-01-01T00:00:00Z
type: task_learnings
confidence: 0.9
branch: main
files: src/foo.py, src/bar.py
categories: coding_conventions, task_learnings
---
The actual memory content text goes here.

"""

from __future__ import annotations

import json
import re
import sys


def parse_blocks(content: str) -> list[dict]:
    """Split content on '---' boundaries and parse each block.

    Returns a list of dicts with keys:
      id, type, confidence, branch, files (list), categories (list), content (str)

    Blocks with empty content are skipped.
    Missing optional fields default to "" (scalar) or [] (list fields).
    """
    # Normalise line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Split on lines that are exactly "---"
    raw_blocks = re.split(r"(?m)^---\s*$", content)

    # After splitting on "---", the structure for each memory is:
    #   raw_blocks[0] = preamble (before first ---, typically empty)
    #   raw_blocks[1] = frontmatter for block 1
    #   raw_blocks[2] = content for block 1
    #   raw_blocks[3] = frontmatter for block 2
    #   raw_blocks[4] = content for block 2
    #   ...
    # So frontmatter blocks are at odd indices (1, 3, 5, ...) and
    # content blocks at even indices (2, 4, 6, ...).

    results: list[dict] = []

    # Pair up frontmatter + content starting at index 1
    i = 1
    while i < len(raw_blocks):
        frontmatter_raw = raw_blocks[i]
        content_raw = raw_blocks[i + 1] if i + 1 < len(raw_blocks) else ""

        # Parse the frontmatter key-value pairs
        fm = _parse_frontmatter(frontmatter_raw)

        # Strip leading/trailing whitespace from content
        memory_content = content_raw.strip()

        # Skip blocks with empty content
        if not memory_content:
            i += 2
            continue

        record = {
            "id": fm.get("id", ""),
            "type": fm.get("type", ""),
            "confidence": fm.get("confidence", ""),
            "branch": fm.get("branch", ""),
            "files": _parse_list_field(fm.get("files", "")),
            "categories": _parse_list_field(fm.get("categories", "")),
            "content": memory_content,
        }

        # Include created_at if present
        if "created_at" in fm:
            record["created_at"] = fm["created_at"]

        results.append(record)
        i += 2

    return results


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse simple 'key: value' lines from frontmatter text.

    Only the first colon is used as the delimiter — values may contain colons.
    Lines not matching 'key: value' are ignored.
    """
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            result[key] = value
    return result


def _parse_list_field(value: str) -> list[str]:
    """Split a comma-separated value into a list, stripping whitespace.

    Returns [] for empty/whitespace-only input.
    """
    if not value or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: parse_export_file.py <path-to-export-file>", file=sys.stderr)
        print("[]")
        sys.exit(0)

    filepath = sys.argv[1]
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        print("[]")
        sys.exit(0)

    records = parse_blocks(content)
    print(json.dumps(records, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
