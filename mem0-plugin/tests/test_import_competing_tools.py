"""Tests for import_competing_tools.py — competing tool file importers."""

from __future__ import annotations

import json
import os
import sys
from unittest import mock

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


# ---------------------------------------------------------------------------
# split_sections tests (unit tests on the splitter functions)
# ---------------------------------------------------------------------------


def test_split_by_headers_cursorrules():
    """split_by_headers correctly splits .cursorrules content on ## headers."""
    from import_competing_tools import split_by_headers

    content = """\
# My Cursor Rules

Some preamble text that belongs to the first section.

## TypeScript Conventions

Always use strict mode. Prefer const over let.
Never use var.

## React Patterns

Use functional components with hooks.
Avoid class components.

## Testing

Write tests for all utility functions.
"""
    chunks = split_by_headers(content, "## ")
    assert len(chunks) == 4  # preamble + 3 sections

    # First chunk is the preamble (before any ## header)
    assert "preamble text" in chunks[0]

    # Remaining chunks start with their header
    assert chunks[1].startswith("## TypeScript Conventions")
    assert "strict mode" in chunks[1]

    assert chunks[2].startswith("## React Patterns")
    assert "functional components" in chunks[2]

    assert chunks[3].startswith("## Testing")
    assert "utility functions" in chunks[3]


def test_split_by_headers_copilot():
    """split_by_headers correctly splits copilot-instructions.md on ## headers."""
    from import_competing_tools import split_by_headers

    content = """\
## Code Style

Use 2-space indentation. Always add trailing commas.

## Architecture

Follow clean architecture principles. Keep business logic in domain layer.
"""
    chunks = split_by_headers(content, "## ")
    assert len(chunks) == 2
    assert chunks[0].startswith("## Code Style")
    assert "2-space indentation" in chunks[0]
    assert chunks[1].startswith("## Architecture")
    assert "clean architecture" in chunks[1]


def test_split_by_headers_no_headers():
    """split_by_headers returns entire content as one chunk if no headers found."""
    from import_competing_tools import split_by_headers

    content = "This file has no headers at all. Just plain text."
    chunks = split_by_headers(content, "## ")
    assert len(chunks) == 1
    assert "Just plain text" in chunks[0]


def test_split_cline_multiple_md_files(tmp_path):
    """cmd_cline processes multiple .md files from memory-bank/ directory."""
    from import_competing_tools import filter_and_truncate

    # Create a temporary memory-bank directory with .md files
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir()

    (mb_dir / "architecture.md").write_text(
        "# Architecture Decisions\n\nUse microservices architecture with event sourcing."
    )
    (mb_dir / "conventions.md").write_text(
        "# Code Conventions\n\nAll functions must have type hints. Use black formatter."
    )
    (mb_dir / "empty.md").write_text("")  # empty file should be skipped

    # Read and verify we can split the files
    md_files = sorted(f for f in os.listdir(str(mb_dir)) if f.endswith(".md"))
    assert "architecture.md" in md_files
    assert "conventions.md" in md_files
    assert "empty.md" in md_files

    non_empty = []
    for filename in md_files:
        filepath = os.path.join(str(mb_dir), filename)
        with open(filepath) as f:
            content = f.read().strip()
        if content:
            chunks = filter_and_truncate([content])
            non_empty.extend(chunks)

    assert len(non_empty) == 2
    assert any("microservices" in c for c in non_empty)
    assert any("type hints" in c for c in non_empty)


def test_split_by_hr_or_headers_continue():
    """split_by_hr_or_headers correctly splits .continue/rules.md."""
    from import_competing_tools import split_by_hr_or_headers

    content = """\
## First Section

Content of first section.

---

## Second Section

Content of second section.

---

Third section without a header (just after HR).
"""
    chunks = split_by_hr_or_headers(content)
    # Should split into meaningful chunks
    assert len(chunks) >= 2
    assert any("First Section" in c for c in chunks)
    assert any("Second Section" in c for c in chunks)


def test_filter_and_truncate_skips_short():
    """filter_and_truncate skips chunks shorter than MIN_CHUNK_CHARS (50)."""
    from import_competing_tools import filter_and_truncate

    chunks = [
        "Short",  # < 50 chars, should be filtered
        "A" * 49,  # exactly 49 chars, should be filtered
        "A" * 50,  # exactly 50 chars, should be kept
        "A long enough chunk that definitely passes the minimum length filter.",
    ]
    result = filter_and_truncate(chunks)
    assert len(result) == 2
    assert all(len(c) >= 50 for c in result)


def test_filter_and_truncate_truncates_long():
    """filter_and_truncate truncates chunks over MAX_CHUNK_CHARS (10000)."""
    from import_competing_tools import MAX_CHUNK_CHARS, filter_and_truncate

    long_chunk = "X" * (MAX_CHUNK_CHARS + 500)
    result = filter_and_truncate([long_chunk])
    assert len(result) == 1
    assert len(result[0]) == MAX_CHUNK_CHARS


# ---------------------------------------------------------------------------
# Mock API tests
# ---------------------------------------------------------------------------


def _make_mock_response(status: int = 201, body: dict | None = None) -> mock.MagicMock:
    """Create a mock HTTP response object."""
    if body is None:
        body = {"id": "new-mem-id", "memory": "test"}
    resp = mock.MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(body).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = mock.MagicMock(return_value=False)
    return resp


def test_cursorrules_import_api_call(tmp_path):
    """cmd_cursorrules calls the API with correct app_id (top-level), infer=False, and correct source."""
    from import_competing_tools import cmd_cursorrules

    # Create a .cursorrules file with enough content
    cursorrules = tmp_path / ".cursorrules"
    cursorrules.write_text(
        "## TypeScript Rules\n\nAlways use strict TypeScript. Never use 'any' type. "
        "Prefer interfaces over type aliases for object shapes."
    )

    captured_requests: list[dict] = []

    def mock_urlopen(req, timeout=None):
        body = json.loads(req.data.decode())
        captured_requests.append(body)
        return _make_mock_response(201)

    with mock.patch("import_competing_tools.resolve_api_key", return_value="m0-testkey"), \
         mock.patch("import_competing_tools.resolve_user_id", return_value="testuser"), \
         mock.patch("import_competing_tools.resolve_project_id", return_value="my-project"), \
         mock.patch("import_competing_tools.resolve_branch", return_value="main"), \
         mock.patch("urllib.request.urlopen", side_effect=mock_urlopen):

        original_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            cmd_cursorrules(["--path", str(cursorrules)])
        finally:
            os.chdir(original_cwd)

    assert len(captured_requests) >= 1

    req_body = captured_requests[0]

    # app_id must be top-level (not inside metadata)
    assert req_body["app_id"] == "my-project", f"Expected app_id at top level, got: {req_body}"

    # infer must be False (not "false", but the boolean False)
    assert req_body["infer"] is False, f"Expected infer=False, got: {req_body['infer']}"

    # source must be cursor-import
    assert req_body["metadata"]["source"] == "cursor-import", (
        f"Expected source=cursor-import, got: {req_body['metadata'].get('source')}"
    )

    # user_id must be set
    assert req_body["user_id"] == "testuser"

    # messages must be a list with role/content
    assert isinstance(req_body["messages"], list)
    assert req_body["messages"][0]["role"] == "user"
    assert len(req_body["messages"][0]["content"]) > 0


def test_copilot_import_api_call(tmp_path):
    """cmd_copilot calls the API with source=copilot-import."""
    from import_competing_tools import cmd_copilot

    copilot_dir = tmp_path / ".github"
    copilot_dir.mkdir()
    copilot_file = copilot_dir / "copilot-instructions.md"
    copilot_file.write_text(
        "## Code Style\n\nUse 2-space indentation. Always add trailing commas in multi-line structures. "
        "Prefer const over let. Never use var in JavaScript code."
    )

    captured: list[dict] = []

    def mock_urlopen(req, timeout=None):
        captured.append(json.loads(req.data.decode()))
        return _make_mock_response(201)

    with mock.patch("import_competing_tools.resolve_api_key", return_value="m0-key"), \
         mock.patch("import_competing_tools.resolve_user_id", return_value="user1"), \
         mock.patch("import_competing_tools.resolve_project_id", return_value="proj1"), \
         mock.patch("import_competing_tools.resolve_branch", return_value="main"), \
         mock.patch("urllib.request.urlopen", side_effect=mock_urlopen):

        cmd_copilot(["--path", str(copilot_file)])

    assert len(captured) >= 1
    assert captured[0]["metadata"]["source"] == "copilot-import"
    assert captured[0]["app_id"] == "proj1"
    assert captured[0]["infer"] is False


def test_cline_import_multiple_files(tmp_path):
    """cmd_cline imports one memory per non-empty .md file."""
    from import_competing_tools import cmd_cline

    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "arch.md").write_text(
        "Architecture: microservices with event-sourcing. Each service owns its database. "
        "Communication via message bus only. No direct service-to-service HTTP calls."
    )
    (mb / "style.md").write_text(
        "Code style: PEP 8 for Python. Black formatter. isort for imports. "
        "Line length 120. Type hints required on all public functions and methods."
    )
    (mb / "empty.md").write_text("")

    captured: list[dict] = []

    def mock_urlopen(req, timeout=None):
        captured.append(json.loads(req.data.decode()))
        return _make_mock_response(201)

    with mock.patch("import_competing_tools.resolve_api_key", return_value="m0-key"), \
         mock.patch("import_competing_tools.resolve_user_id", return_value="user1"), \
         mock.patch("import_competing_tools.resolve_project_id", return_value="proj1"), \
         mock.patch("import_competing_tools.resolve_branch", return_value="main"), \
         mock.patch("urllib.request.urlopen", side_effect=mock_urlopen):

        cmd_cline(["--path", str(mb)])

    # Should have exactly 2 imports (empty.md skipped)
    assert len(captured) == 2
    sources = {r["metadata"]["source"] for r in captured}
    assert sources == {"cline-import"}
    for r in captured:
        assert r["infer"] is False
        assert r["app_id"] == "proj1"


def test_no_api_key_does_not_call_api(tmp_path):
    """When no API key is set, no HTTP call is made."""
    from import_competing_tools import cmd_cursorrules

    cursorrules = tmp_path / ".cursorrules"
    cursorrules.write_text("## Rules\n\n" + "x" * 100)

    with mock.patch("import_competing_tools.resolve_api_key", return_value=""), \
         mock.patch("urllib.request.urlopen") as mock_url:

        cmd_cursorrules(["--path", str(cursorrules)])

    mock_url.assert_not_called()


def test_missing_file_does_not_call_api(tmp_path):
    """When the source file doesn't exist, no HTTP call is made."""
    from import_competing_tools import cmd_cursorrules

    with mock.patch("import_competing_tools.resolve_api_key", return_value="m0-key"), \
         mock.patch("urllib.request.urlopen") as mock_url:

        cmd_cursorrules(["--path", str(tmp_path / "nonexistent.cursorrules")])

    mock_url.assert_not_called()


def test_main_unknown_subcommand_exits_zero():
    """Calling main() with an unknown subcommand exits 0."""
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "import_competing_tools.py"), "unknown"],
        capture_output=True,
        text=True,
        env={**os.environ, "MEM0_API_KEY": ""},
    )
    assert result.returncode == 0
