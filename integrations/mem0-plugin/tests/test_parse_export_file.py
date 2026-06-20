"""Tests for parse_export_file.py — mem0 export file parser."""

from __future__ import annotations

import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


# ---------------------------------------------------------------------------
# Direct function tests
# ---------------------------------------------------------------------------


def test_parse_blocks_single_valid_block():
    """parse_blocks returns one record for a single valid block."""
    from parse_export_file import parse_blocks

    content = """\
---
id: abc123
created_at: 2024-01-15T10:00:00Z
type: task_learnings
confidence: 0.85
branch: main
files: src/foo.py, src/bar.py
categories: coding_conventions, task_learnings
---
Always use context managers when opening files.
"""
    records = parse_blocks(content)
    assert len(records) == 1
    r = records[0]
    assert r["id"] == "abc123"
    assert r["type"] == "task_learnings"
    assert r["confidence"] == "0.85"
    assert r["branch"] == "main"
    assert r["files"] == ["src/foo.py", "src/bar.py"]
    assert r["categories"] == ["coding_conventions", "task_learnings"]
    assert "Always use context managers" in r["content"]


def test_parse_blocks_multiple_blocks():
    """parse_blocks returns the correct number of records for multiple blocks."""
    from parse_export_file import parse_blocks

    content = """\
---
id: mem001
type: architecture_decisions
confidence: 0.9
branch: main
files:
categories: architecture_decisions
---
Use hexagonal architecture for the core domain.

---
id: mem002
type: anti_patterns
confidence: 0.75
branch: feat/refactor
files: src/legacy.py
categories: anti_patterns
---
Avoid direct database calls from view layer.

---
id: mem003
type: coding_conventions
confidence: 0.8
branch: main
files: src/utils.py, src/helpers.py
categories:
---
Use snake_case for all Python identifiers.
"""
    records = parse_blocks(content)
    assert len(records) == 3

    assert records[0]["id"] == "mem001"
    assert records[0]["categories"] == ["architecture_decisions"]
    assert "hexagonal architecture" in records[0]["content"]

    assert records[1]["id"] == "mem002"
    assert records[1]["files"] == ["src/legacy.py"]
    assert "direct database calls" in records[1]["content"]

    assert records[2]["id"] == "mem003"
    assert records[2]["files"] == ["src/utils.py", "src/helpers.py"]
    assert records[2]["categories"] == []
    assert "snake_case" in records[2]["content"]


def test_parse_blocks_missing_optional_fields():
    """parse_blocks uses defaults when optional fields are absent."""
    from parse_export_file import parse_blocks

    # confidence, branch, files, categories all absent
    content = """\
---
id: xyz789
type: task_learnings
---
Run tests before committing.
"""
    records = parse_blocks(content)
    assert len(records) == 1
    r = records[0]
    assert r["id"] == "xyz789"
    assert r["confidence"] == ""   # default empty string
    assert r["branch"] == ""       # default empty string
    assert r["files"] == []        # default empty list
    assert r["categories"] == []   # default empty list
    assert "Run tests" in r["content"]


def test_parse_blocks_filters_empty_content():
    """parse_blocks skips blocks whose content is empty or whitespace-only."""
    from parse_export_file import parse_blocks

    content = """\
---
id: empty1
type: task_learnings
---

---
id: real1
type: task_learnings
---
This block has real content.

---
id: empty2
type: coding_conventions
---

"""
    records = parse_blocks(content)
    # Only the block with actual content should be returned
    assert len(records) == 1
    assert records[0]["id"] == "real1"
    assert "real content" in records[0]["content"]


def test_parse_blocks_round_trip():
    """Content formatted by export matches what parse_blocks expects."""
    from parse_export_file import parse_blocks

    # Simulate the exact format produced by the export skill
    memory_id = "test-id-001"
    created_at = "2024-06-01T12:00:00Z"
    mem_type = "architecture_decisions"
    confidence = "0.92"
    branch = "feat/new-feature"
    files = ["src/main.py", "tests/test_main.py"]
    categories = ["architecture_decisions", "coding_conventions"]
    memory_content = "Use dependency injection for all service classes."

    # Format exactly as the export skill would
    block = (
        "---\n"
        f"id: {memory_id}\n"
        f"created_at: {created_at}\n"
        f"type: {mem_type}\n"
        f"confidence: {confidence}\n"
        f"branch: {branch}\n"
        f"files: {', '.join(files)}\n"
        f"categories: {', '.join(categories)}\n"
        "---\n"
        f"{memory_content}\n"
        "\n"
    )

    records = parse_blocks(block)
    assert len(records) == 1
    r = records[0]
    assert r["id"] == memory_id
    assert r["type"] == mem_type
    assert r["confidence"] == confidence
    assert r["branch"] == branch
    assert r["files"] == files
    assert r["categories"] == categories
    assert r["content"] == memory_content


def test_parse_blocks_multiline_content():
    """parse_blocks correctly captures multi-line memory content."""
    from parse_export_file import parse_blocks

    content = """\
---
id: multi001
type: task_learnings
---
Line one of the memory.
Line two of the memory.

Line four after blank line.
"""
    records = parse_blocks(content)
    assert len(records) == 1
    assert "Line one" in records[0]["content"]
    assert "Line two" in records[0]["content"]
    assert "Line four" in records[0]["content"]


def test_parse_blocks_empty_input():
    """parse_blocks returns empty list for empty input."""
    from parse_export_file import parse_blocks

    assert parse_blocks("") == []
    assert parse_blocks("   \n   ") == []


def test_parse_blocks_no_blocks():
    """parse_blocks returns empty list for content without any --- delimiters."""
    from parse_export_file import parse_blocks

    assert parse_blocks("Just some text without any delimiters.") == []


def test_parse_blocks_value_with_colon():
    """parse_blocks handles values that themselves contain colons."""
    from parse_export_file import parse_blocks

    content = """\
---
id: colon-test
type: task_learnings
created_at: 2024-01-01T10:00:00Z
---
Timestamp values contain colons and should parse correctly.
"""
    records = parse_blocks(content)
    assert len(records) == 1
    assert records[0]["id"] == "colon-test"
    # created_at field should be captured (it's in the record if present)
    assert "2024-01-01T10:00:00Z" in records[0].get("created_at", "")


# ---------------------------------------------------------------------------
# CLI / subprocess tests
# ---------------------------------------------------------------------------


def test_main_cli_outputs_json(tmp_path):
    """Running parse_export_file.py as a script outputs valid JSON."""
    export_file = tmp_path / "mem0-export-test.md"
    export_file.write_text("""\
---
id: cli-test-001
type: task_learnings
confidence: 0.8
branch: main
files:
categories: task_learnings
---
Prefer composition over inheritance.
""")

    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "parse_export_file.py"), str(export_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    records = json.loads(result.stdout)
    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0]["id"] == "cli-test-001"


def test_main_cli_no_args_exits_zero():
    """Running parse_export_file.py with no arguments exits 0 and prints []."""
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "parse_export_file.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "[]"


def test_main_cli_missing_file_exits_zero(tmp_path):
    """Running parse_export_file.py with a missing file exits 0 and prints []."""
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "parse_export_file.py"),
         str(tmp_path / "nonexistent.md")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "[]"
