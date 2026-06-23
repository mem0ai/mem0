"""Shared content-chunking utilities for mem0-plugin import scripts."""

from __future__ import annotations

MIN_CHUNK_CHARS = 50
MAX_CHUNK_CHARS = 10_000


def split_by_headers(content: str, header_prefix: str = "## ") -> list[str]:
    """Split content by Markdown header lines (e.g. '## ').

    The header line is included at the start of each chunk.
    Returns a list of non-empty chunk strings.
    """
    chunks: list[str] = []
    current_lines: list[str] = []

    for line in content.splitlines(keepends=True):
        if line.startswith(header_prefix) and current_lines:
            chunk = "".join(current_lines).strip()
            if chunk:
                chunks.append(chunk)
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        chunk = "".join(current_lines).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def split_by_hr_or_headers(content: str) -> list[str]:
    """Split content by '---' horizontal rules or '## ' headers.

    Used for .continue/rules.md which may use either convention.
    """
    import re

    # Split on lines that are exactly "---" or start with "## "
    chunks: list[str] = []
    current_lines: list[str] = []

    for line in content.splitlines(keepends=True):
        is_hr = re.match(r"^---\s*$", line)
        is_h2 = line.startswith("## ")

        if (is_hr or is_h2) and current_lines:
            chunk = "".join(current_lines).strip()
            if chunk:
                chunks.append(chunk)
            current_lines = [] if is_hr else [line]
        else:
            current_lines.append(line)

    if current_lines:
        chunk = "".join(current_lines).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def filter_and_truncate(chunks: list[str]) -> list[str]:
    """Filter out chunks shorter than MIN_CHUNK_CHARS, truncate long chunks."""
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) < MIN_CHUNK_CHARS:
            continue
        if len(chunk) > MAX_CHUNK_CHARS:
            chunk = chunk[:MAX_CHUNK_CHARS]
        result.append(chunk)
    return result
