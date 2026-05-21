"""Tests for parse_mem0_config.py — mem0.md retention policy parser."""

from __future__ import annotations

import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


# ---------------------------------------------------------------------------
# parse_retention — unit tests
# ---------------------------------------------------------------------------


def test_parse_retention_valid_section():
    """parse_retention extracts day-count policies correctly."""
    from parse_mem0_config import parse_retention

    content = """\
# Project Config

## Retention

session_state: 90d
compact_summary: 60d
decision: 180d
"""
    result = parse_retention(content)
    assert result == {
        "session_state": 90,
        "compact_summary": 60,
        "decision": 180,
    }


def test_parse_retention_forever_returns_none():
    """parse_retention maps 'forever' to None."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

user_preference: forever
anti_pattern: forever
session_state: 30d
"""
    result = parse_retention(content)
    assert result["user_preference"] is None
    assert result["anti_pattern"] is None
    assert result["session_state"] == 30


def test_parse_retention_no_section_returns_empty():
    """parse_retention returns {} when there is no ## Retention heading."""
    from parse_mem0_config import parse_retention

    content = """\
# Project Config

## Some Other Section

key: value
"""
    result = parse_retention(content)
    assert result == {}


def test_parse_retention_stops_at_next_heading():
    """parse_retention stops reading at the next ## heading."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

session_state: 7d

## Other Section

other_key: 999d
"""
    result = parse_retention(content)
    assert "session_state" in result
    assert "other_key" not in result


def test_parse_retention_malformed_lines_skipped():
    """Malformed lines (no colon, bad day format) are silently ignored."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

session_state: 90d
bad_line_no_colon
another: badvalue
decision: 30d
"""
    result = parse_retention(content)
    assert result == {"session_state": 90, "decision": 30}


def test_parse_retention_comments_ignored():
    """Inline # comments are stripped before parsing."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

session_state: 90d  # rolling 90-day window
user_preference: forever  # never prune preferences
"""
    result = parse_retention(content)
    assert result["session_state"] == 90
    assert result["user_preference"] is None


def test_parse_retention_case_insensitive_heading():
    """## retention (lowercase) is matched the same as ## Retention."""
    from parse_mem0_config import parse_retention

    content = """\
## retention

session_state: 14d
"""
    result = parse_retention(content)
    assert result == {"session_state": 14}


def test_parse_retention_empty_section_returns_empty():
    """A ## Retention section with no valid lines returns {}."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

# only comments here

## Next Section
"""
    result = parse_retention(content)
    assert result == {}


# ---------------------------------------------------------------------------
# load_retention_policies — integration tests with tmp files
# ---------------------------------------------------------------------------


def test_load_retention_policies_with_tmp_file(tmp_path):
    """load_retention_policies reads a real mem0.md from disk."""
    from parse_mem0_config import load_retention_policies

    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text(
        """\
# My Project

## Retention

session_state: 90d
compact_summary: 60d
decision: forever
""",
        encoding="utf-8",
    )

    result = load_retention_policies(str(tmp_path))
    assert result == {
        "session_state": 90,
        "compact_summary": 60,
        "decision": None,
    }


def test_load_retention_policies_no_mem0_md_returns_empty(tmp_path):
    """load_retention_policies returns {} when no mem0.md exists."""
    from parse_mem0_config import load_retention_policies

    result = load_retention_policies(str(tmp_path))
    assert result == {}


def test_load_retention_policies_no_retention_section_returns_empty(tmp_path):
    """load_retention_policies returns {} when mem0.md has no ## Retention."""
    from parse_mem0_config import load_retention_policies

    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text(
        """\
# My Project

Some general project notes here.
No retention section.
""",
        encoding="utf-8",
    )

    result = load_retention_policies(str(tmp_path))
    assert result == {}


def test_load_retention_policies_defaults_to_cwd(tmp_path, monkeypatch):
    """load_retention_policies uses os.getcwd() when cwd is None."""
    from parse_mem0_config import load_retention_policies

    monkeypatch.chdir(tmp_path)
    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text("## Retention\nsession_state: 45d\n", encoding="utf-8")

    result = load_retention_policies()  # no cwd arg
    assert result == {"session_state": 45}


# ---------------------------------------------------------------------------
# CLI / main() — subprocess test
# ---------------------------------------------------------------------------


def test_cli_main_prints_json(tmp_path):
    """CLI: python parse_mem0_config.py <cwd> prints valid JSON."""
    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text(
        "## Retention\nsession_state: 90d\nuser_preference: forever\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "parse_mem0_config.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["session_state"] == 90
    assert data["user_preference"] is None


def test_cli_main_no_file_prints_empty_json(tmp_path):
    """CLI: prints '{}' when no mem0.md exists."""
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "parse_mem0_config.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
