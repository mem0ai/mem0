# Claude State Holistic Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-shot importer to `mem0-plugin` that backfills the user's existing CLAUDE.md hierarchy, `.claude/rules`, and `~/.claude/projects/*/memory` + `~/.claude/agent-memory/*` content into mem0 as searchable memories.

**Architecture:** One new Python script (`mem0-plugin/scripts/import_claude_state.py`, patterned on the existing `on_pre_compact.py`) + one new conditional block in the existing `on_session_start.sh` hook + one JSON marker file at `~/.mem0/imports/claude-state.json`. The script does discovery → heading-based chunking → tagging → sequential POST to `https://api.mem0.ai/v1/memories/` with per-chunk marker writes for idempotent re-runs. The hook nudges the agent on first run; the agent invokes the script via `Bash`.

**Tech Stack:** Python 3.9+ stdlib only (urllib, json, hashlib, pathlib, re, argparse, logging, dataclasses) — no new dependencies. pytest + `unittest.mock` for tests. Reuses `_identity.py` and the urllib REST pattern from `on_pre_compact.py`.

**Spec:** [`docs/superpowers/specs/2026-05-18-claude-state-holistic-import-design.md`](../specs/2026-05-18-claude-state-holistic-import-design.md)

---

## File map

| Action | Path | Purpose |
|---|---|---|
| Create | `mem0-plugin/scripts/import_claude_state.py` | Discovery + chunking + dispatch + marker engine (~350 lines). |
| Modify | `mem0-plugin/scripts/on_session_start.sh` | Add ~15-line "Holistic import available" block after existing bootstrap output. |
| Create | `tests/plugin_scripts/__init__.py` | Empty — marks directory as a Python package for pytest discovery. |
| Create | `tests/plugin_scripts/conftest.py` | Adds `mem0-plugin/scripts/` to `sys.path` so tests can import the script directly. |
| Create | `tests/plugin_scripts/test_import_claude_state.py` | All unit + integration tests (~600 lines). |

The marker file `~/.mem0/imports/claude-state.json` is created at runtime by the script — not checked in.

---

## Task 1: Scaffold the script and test harness

**Files:**
- Create: `mem0-plugin/scripts/import_claude_state.py`
- Create: `tests/plugin_scripts/__init__.py`
- Create: `tests/plugin_scripts/conftest.py`
- Create: `tests/plugin_scripts/test_import_claude_state.py`

The goal is to lay down the minimal scaffold so pytest can discover and import the module — every later task adds tests + implementation to these files.

- [ ] **Step 1: Write the smoke test**

Create `tests/plugin_scripts/__init__.py` as an empty file:

```python
```

Create `tests/plugin_scripts/conftest.py`:

```python
"""Make the plugin scripts directory importable by tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "mem0-plugin" / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
```

Create `tests/plugin_scripts/test_import_claude_state.py`:

```python
"""Tests for mem0-plugin/scripts/import_claude_state.py."""

from __future__ import annotations


def test_module_imports():
    """Scaffold smoke test: the module loads without error."""
    import import_claude_state  # noqa: F401
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'import_claude_state'`.

- [ ] **Step 3: Create the minimal script scaffold**

Create `mem0-plugin/scripts/import_claude_state.py`:

```python
#!/usr/bin/env python3
"""Holistic import of on-disk Claude state into mem0.

Backfills CLAUDE.md hierarchy (+ @imports), .claude/rules, and the
~/.claude/projects/*/memory + ~/.claude/agent-memory/* directories.

Patterned on on_pre_compact.py: urllib-based POSTs, stderr logging,
_identity.resolve_user_id() for user_id, and an optional
~/.mem0/hooks.log when MEM0_DEBUG is set.

Invocation:
  python3 import_claude_state.py [--dry-run] [--reset] [--no-infer]
                                 [--source TYPE]

Exit codes:
  0 = success (including dry-run, no-op, partial failures)
  1 = fatal (missing MEM0_API_KEY, auth failure, unreadable marker)
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

log = logging.getLogger("mem0-import-claude-state")
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("[mem0-import-claude-state] %(message)s"))
log.addHandler(_handler)

if os.environ.get("MEM0_DEBUG"):
    _log_dir = os.path.expanduser("~/.mem0")
    try:
        os.makedirs(_log_dir, exist_ok=True)
        _file_handler = logging.FileHandler(os.path.join(_log_dir, "hooks.log"))
        _file_handler.setFormatter(
            logging.Formatter("[mem0-import-claude-state] %(asctime)s %(message)s")
        )
        log.addHandler(_file_handler)
    except OSError:
        pass


def main() -> int:
    """Entry point. Implementations land in later tasks."""
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Make it executable:

```bash
chmod +x mem0-plugin/scripts/import_claude_state.py
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/
git commit -m "feat(plugin): scaffold import_claude_state.py + test harness"
```

---

## Task 2: Marker file I/O

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

Marker reads must tolerate missing files and corrupted JSON (returning an empty marker so the run continues). Writes are atomic (temp file + rename).

- [ ] **Step 1: Write the failing tests**

Append to `tests/plugin_scripts/test_import_claude_state.py`:

```python
import json
from pathlib import Path

import import_claude_state as ics


def test_read_marker_missing_returns_empty(tmp_path: Path):
    marker_path = tmp_path / "claude-state.json"
    assert ics.read_marker(marker_path) == {"schema_version": 1, "imports": []}


def test_read_marker_corrupted_returns_empty(tmp_path: Path, caplog):
    marker_path = tmp_path / "claude-state.json"
    marker_path.write_text("{not valid json")
    with caplog.at_level("WARNING"):
        result = ics.read_marker(marker_path)
    assert result == {"schema_version": 1, "imports": []}
    assert any("corrupted" in r.message.lower() for r in caplog.records)


def test_write_marker_then_read_roundtrip(tmp_path: Path):
    marker_path = tmp_path / "claude-state.json"
    payload = {
        "schema_version": 1,
        "user_id": "alice",
        "last_run_at": "2026-05-18T17:55:00Z",
        "imports": [
            {
                "file": "/tmp/CLAUDE.md",
                "source_type": "claude_md_user",
                "imported_at": "2026-05-18T17:55:00Z",
                "chunks": [
                    {"heading": "Rules", "content_hash": "ab12", "memory_ids": ["m_1"]}
                ],
            }
        ],
    }
    ics.write_marker(marker_path, payload)
    assert ics.read_marker(marker_path) == payload


def test_write_marker_is_atomic(tmp_path: Path, monkeypatch):
    """write_marker must write to a temp file then rename — no partial file
    visible at the final path if the process is killed mid-write."""
    marker_path = tmp_path / "claude-state.json"
    real_replace = os.replace
    calls = {"renamed": False, "temp_paths": []}

    def fake_replace(src, dst):
        calls["renamed"] = True
        calls["temp_paths"].append(str(src))
        return real_replace(src, dst)

    monkeypatch.setattr(ics.os, "replace", fake_replace)
    ics.write_marker(marker_path, {"schema_version": 1, "imports": []})
    assert calls["renamed"] is True
    assert calls["temp_paths"][0].endswith(".tmp")
    assert marker_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "marker"`
Expected: 4 FAILs with `AttributeError: module 'import_claude_state' has no attribute 'read_marker'`.

- [ ] **Step 3: Implement marker I/O**

Append to `mem0-plugin/scripts/import_claude_state.py` (after the logging setup, before `main`):

```python
import json
import tempfile
from pathlib import Path
from typing import Any

MARKER_PATH = Path.home() / ".mem0" / "imports" / "claude-state.json"
EMPTY_MARKER: dict[str, Any] = {"schema_version": 1, "imports": []}


def read_marker(path: Path) -> dict[str, Any]:
    """Read the import marker, tolerating missing or corrupted files."""
    if not path.exists():
        return dict(EMPTY_MARKER)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "imports" not in data:
            log.warning("Marker file at %s has unexpected shape, treating as empty", path)
            return dict(EMPTY_MARKER)
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Marker file at %s is corrupted (%s), treating as empty", path, e)
        return dict(EMPTY_MARKER)


def write_marker(path: Path, marker: dict[str, Any]) -> None:
    """Atomically write the marker file (temp + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(marker, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "marker"`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): marker file I/O for claude-state import (atomic write, corruption-tolerant read)"
```

---

## Task 3: Markdown chunker — basic splits

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

Split markdown at `## ` (H2) by default. Each chunk gets a SHA-256 content hash. Handle the edge cases: no headings (one chunk), only H1 (still one chunk — H1 is title, not a section divider).

- [ ] **Step 1: Write the failing tests**

Append to `tests/plugin_scripts/test_import_claude_state.py`:

```python
import hashlib


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_chunk_markdown_no_headings_returns_one_chunk():
    text = "Just some plain text without any headings.\nA second line."
    chunks = ics.chunk_markdown(text)
    assert len(chunks) == 1
    assert chunks[0].heading == ""
    assert chunks[0].body == text
    assert chunks[0].content_hash == _sha256(text)


def test_chunk_markdown_only_h1_returns_one_chunk():
    text = "# Title\n\nIntro paragraph.\nAnother line."
    chunks = ics.chunk_markdown(text)
    assert len(chunks) == 1
    assert chunks[0].heading == "Title"
    assert "Intro paragraph" in chunks[0].body


def test_chunk_markdown_splits_on_h2():
    text = (
        "# Title\n\n"
        "Intro.\n\n"
        "## Section A\n\n"
        "Body of A.\n\n"
        "## Section B\n\n"
        "Body of B.\n"
    )
    chunks = ics.chunk_markdown(text)
    assert len(chunks) == 3  # intro under H1, then A, then B
    assert chunks[0].heading == "Title"
    assert "Intro." in chunks[0].body
    assert chunks[1].heading == "Section A"
    assert "Body of A." in chunks[1].body
    assert chunks[2].heading == "Section B"
    assert "Body of B." in chunks[2].body


def test_chunk_markdown_content_hash_deterministic():
    text = "## Heading\nBody."
    a = ics.chunk_markdown(text)
    b = ics.chunk_markdown(text)
    assert a[0].content_hash == b[0].content_hash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "chunk"`
Expected: 4 FAILs with `AttributeError: module 'import_claude_state' has no attribute 'chunk_markdown'`.

- [ ] **Step 3: Implement basic chunker**

Append to `mem0-plugin/scripts/import_claude_state.py` (after marker I/O, before `main`):

```python
import hashlib
import re
from dataclasses import dataclass

H2_LINE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
H1_LINE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Chunk:
    heading: str
    body: str
    content_hash: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_chunk(heading: str, body: str) -> Chunk:
    body = body.strip("\n")
    return Chunk(heading=heading, body=body, content_hash=_sha256(body))


def _split_on_h2(text: str) -> list[tuple[str, str]]:
    """Return a list of (heading, body) tuples split at H2 boundaries.

    Content before the first H2 becomes one chunk with heading derived from
    the H1 (if present) or "" otherwise.
    """
    matches = list(H2_LINE.finditer(text))
    if not matches:
        h1 = H1_LINE.search(text)
        heading = h1.group(1).strip() if h1 else ""
        return [(heading, text)]

    sections: list[tuple[str, str]] = []
    first = matches[0]
    preamble = text[: first.start()]
    if preamble.strip():
        h1 = H1_LINE.search(preamble)
        heading = h1.group(1).strip() if h1 else ""
        sections.append((heading, preamble))

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        body_start = m.start()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        sections.append((heading, body))
    return sections


def chunk_markdown(text: str) -> list[Chunk]:
    """Split markdown into Chunks. Future tasks add size/code-fence handling."""
    sections = _split_on_h2(text)
    return [_make_chunk(h, b) for h, b in sections]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "chunk"`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): chunk_markdown basic H2 splits + content_hash"
```

---

## Task 4: Chunker — descend to H3 on oversize, merge small siblings

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

H2 sections exceeding `MAX_CHARS_PER_CHUNK = 2000` chars get re-split at H3. Adjacent chunks under `MIN_CHARS_PER_CHUNK = 200` chars under the same parent are merged.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_chunk_markdown_oversize_h2_descends_to_h3():
    big_body_a = "Filler text. " * 200  # ~2600 chars, exceeds MAX
    big_body_b = "More filler. " * 200
    text = (
        "## Big Section\n\n"
        f"{big_body_a}\n\n"
        "### Subsection A\n\n"
        f"{big_body_a}\n\n"
        "### Subsection B\n\n"
        f"{big_body_b}\n"
    )
    chunks = ics.chunk_markdown(text)
    # Should NOT keep the whole thing as one ~5000+ char chunk.
    headings = [c.heading for c in chunks]
    assert "Subsection A" in headings
    assert "Subsection B" in headings
    # Each emitted chunk should be under the max (with a small buffer for
    # heading lines + whitespace).
    for c in chunks:
        assert len(c.body) <= 2400, f"chunk too big: {len(c.body)} chars"


def test_chunk_markdown_merges_small_siblings():
    text = (
        "## A\n\nshort\n\n"
        "## B\n\nshort\n\n"
        "## C\n\nshort\n"
    )
    chunks = ics.chunk_markdown(text)
    # Three siblings each ~10 chars body should collapse into fewer chunks
    # (under the 200-char min, they merge).
    assert len(chunks) < 3
    # The merged chunk's heading is the first H2 in the merge group.
    assert chunks[0].heading == "A"
    # And the body contains content from all merged siblings.
    assert "B" in chunks[0].body
    assert "C" in chunks[0].body


def test_chunk_markdown_does_not_merge_below_min_when_already_at_h3():
    """If we descended to H3 because the parent was oversize, small H3 children
    should still be emitted (merging back to H2 would reverse the descent)."""
    big = "x" * 2500
    text = (
        f"## Parent\n\n{big}\n\n"
        "### Sub 1\n\ntiny 1\n\n"
        "### Sub 2\n\ntiny 2\n"
    )
    chunks = ics.chunk_markdown(text)
    headings = [c.heading for c in chunks]
    # We descended; Sub 1 and Sub 2 may merge with each other (siblings), but
    # they shouldn't fold back into Parent's oversized body.
    assert any(h.startswith("Sub") for h in headings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "oversize or merges or not_merge"`
Expected: 3 FAILs.

- [ ] **Step 3: Implement oversize descent + sibling merge**

Replace the existing `chunk_markdown` and `_split_on_h2` block with:

```python
H2_LINE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
H3_LINE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
H1_LINE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

MAX_CHARS_PER_CHUNK = 2000
MIN_CHARS_PER_CHUNK = 200


def _split_on_pattern(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    """Generic heading-splitter for either H2 or H3 patterns."""
    matches = list(pattern.finditer(text))
    if not matches:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    first = matches[0]
    preamble = text[: first.start()]
    if preamble.strip():
        h1 = H1_LINE.search(preamble)
        heading = h1.group(1).strip() if h1 else ""
        sections.append((heading, preamble))

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        body_start = m.start()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        sections.append((heading, body))
    return sections


def _descend_oversized(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """For any section whose body exceeds MAX_CHARS_PER_CHUNK, re-split at H3."""
    result: list[tuple[str, str]] = []
    for heading, body in sections:
        if len(body) <= MAX_CHARS_PER_CHUNK:
            result.append((heading, body))
            continue
        h3_subs = _split_on_pattern(body, H3_LINE)
        if len(h3_subs) <= 1:
            # No H3s inside; keep oversized chunk as-is (we don't break
            # paragraphs mid-text — preserving wording matters).
            result.append((heading, body))
        else:
            result.extend(h3_subs)
    return result


def _merge_small_siblings(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge adjacent chunks whose body is under MIN_CHARS_PER_CHUNK.

    The merged chunk keeps the FIRST sibling's heading and concatenates the
    bodies in order.
    """
    if not sections:
        return sections
    merged: list[tuple[str, str]] = []
    buf_heading, buf_body = sections[0]
    for heading, body in sections[1:]:
        combined_len = len(buf_body) + len(body)
        if len(buf_body.strip()) < MIN_CHARS_PER_CHUNK and combined_len <= MAX_CHARS_PER_CHUNK:
            buf_body = buf_body + "\n\n" + body
        else:
            merged.append((buf_heading, buf_body))
            buf_heading, buf_body = heading, body
    merged.append((buf_heading, buf_body))
    return merged


def chunk_markdown(text: str) -> list[Chunk]:
    """Split markdown into Chunks.

    Order of operations:
      1. Split at H2.
      2. For each section over MAX_CHARS_PER_CHUNK, re-split at H3.
      3. Merge adjacent sections whose body is under MIN_CHARS_PER_CHUNK
         (provided the merged size still fits in MAX_CHARS_PER_CHUNK).
    """
    sections = _split_on_pattern(text, H2_LINE)
    sections = _descend_oversized(sections)
    sections = _merge_small_siblings(sections)
    return [_make_chunk(h, b) for h, b in sections]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "chunk"`
Expected: all chunk tests pass (basic + new ones, 7 total at this point).

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): chunk_markdown descends to H3 on oversize, merges small siblings"
```

---

## Task 5: Chunker — protect code fences from being split

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

A fenced code block (``` ``` ```) that happens to contain `## ` text must not trigger a split. Apply a pre-pass that masks fence regions.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_chunk_markdown_does_not_split_inside_code_fence():
    text = (
        "## Real Section\n\n"
        "Body before code.\n\n"
        "```bash\n"
        "## This looks like an H2 but it's inside a fence\n"
        "echo hello\n"
        "```\n\n"
        "Body after code.\n"
    )
    chunks = ics.chunk_markdown(text)
    assert len(chunks) == 1
    assert "## This looks like an H2" in chunks[0].body


def test_chunk_markdown_handles_nested_fences_with_tilde():
    text = (
        "## A\n\n"
        "~~~python\n"
        "## still inside\n"
        "~~~\n\n"
        "## B\n\n"
        "Real B.\n"
    )
    chunks = ics.chunk_markdown(text)
    headings = [c.heading for c in chunks]
    assert headings == ["A", "B"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "code_fence or tilde"`
Expected: 2 FAILs — the chunker is splitting inside fences.

- [ ] **Step 3: Implement fence masking**

Add to `mem0-plugin/scripts/import_claude_state.py` (above `_split_on_pattern`):

```python
FENCE_LINE = re.compile(r"^(```+|~~~+)", re.MULTILINE)


def _mask_fences(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Replace heading-like lines inside code fences with placeholder content
    so they don't trigger heading splits. Returns the masked text plus the
    fence ranges (kept for debugging; not strictly needed by the caller)."""
    fences: list[tuple[int, int]] = []
    fence_open: tuple[int, str] | None = None  # (start_offset, marker)
    out: list[str] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        m = FENCE_LINE.match(stripped)
        if m:
            marker = m.group(1)[:3]  # ``` or ~~~
            if fence_open is None:
                fence_open = (offset, marker)
                out.append(line)
            elif fence_open[1] in marker:
                fences.append((fence_open[0], offset + len(line)))
                fence_open = None
                out.append(line)
            else:
                out.append(line)
        elif fence_open is not None and stripped.startswith("#"):
            # Replace leading # with a non-heading char so the regex misses it.
            out.append("\\" + line)
        else:
            out.append(line)
        offset += len(line)
    if fence_open is not None:
        fences.append((fence_open[0], offset))
    return "".join(out), fences
```

Modify `chunk_markdown` to use the masked text for splitting, but emit the **original** body in chunks:

```python
def chunk_markdown(text: str) -> list[Chunk]:
    """Split markdown into Chunks.

    Order:
      1. Mask heading-like lines inside fenced code blocks (``` or ~~~).
      2. Split the masked text at H2.
      3. For sections over MAX_CHARS_PER_CHUNK, re-split at H3.
      4. Merge adjacent sections under MIN_CHARS_PER_CHUNK.
      5. Map each masked-text section back to a slice of the ORIGINAL text
         (so chunk bodies preserve the user's wording exactly).
    """
    masked, _fences = _mask_fences(text)
    sections = _split_on_pattern(masked, H2_LINE)
    sections = _descend_oversized(sections)
    sections = _merge_small_siblings(sections)

    # Re-derive bodies from the original text using offsets.
    # Since masked has the same length as text (we only swap chars, never
    # add/remove), offsets are preserved 1:1.
    assert len(masked) == len(text), "fence masking must preserve length"
    result: list[Chunk] = []
    cursor = 0
    for heading, masked_body in sections:
        # Find the masked_body inside masked starting at cursor — since splits
        # are contiguous and ordered, each body starts at the previous one's end.
        end = cursor + len(masked_body)
        original_body = text[cursor:end]
        result.append(_make_chunk(heading, original_body))
        cursor = end
    return result
```

> **Heads-up on the length invariant:** `_mask_fences` must replace inside-fence `#` characters with another single character (not add or remove anything) so the masked text has the same offsets as the original. The current implementation prepends `\` — fix that to keep length equal by replacing the first character instead. Update `_mask_fences` accordingly:

```python
        elif fence_open is not None and stripped.startswith("#"):
            # Replace the leading '#' with a space — same length, no longer
            # matches the heading regex.
            idx = len(line) - len(stripped)
            out.append(line[:idx] + " " + line[idx + 1 :])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "chunk"`
Expected: all chunk tests pass (9 total now).

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): chunk_markdown protects code-fenced ## from splitting"
```

---

## Task 6: Source typing + tagger

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

The `tag_chunk` function returns the metadata dict attached to each `add_memory` POST. Source type determines the default `type`; heading keywords override it.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_tag_chunk_claude_md_defaults_to_convention():
    src = ics.Source(
        path=Path("/Users/alice/CLAUDE.md"),
        source_type="claude_md_user",
    )
    chunk = ics.Chunk(heading="Coding Standards", body="...", content_hash="x")
    md = ics.tag_chunk(src, chunk)
    assert md["source_type"] == "claude_md_user"
    assert md["source_file"] == "/Users/alice/CLAUDE.md"
    assert md["section_heading"] == "Coding Standards"
    assert md["content_hash"] == "x"
    assert md["type"] == "convention"


def test_tag_chunk_claude_md_preference_keyword_override():
    src = ics.Source(path=Path("/p/CLAUDE.md"), source_type="claude_md_project")
    chunk = ics.Chunk(heading="My Preferences", body="...", content_hash="x")
    md = ics.tag_chunk(src, chunk)
    assert md["type"] == "user_preference"


def test_tag_chunk_memory_md_default_is_task_learning():
    src = ics.Source(
        path=Path("/Users/alice/.claude/projects/p/memory/MEMORY.md"),
        source_type="memory_md",
        project_name="p",
    )
    chunk = ics.Chunk(heading="Build commands", body="...", content_hash="x")
    md = ics.tag_chunk(src, chunk)
    assert md["type"] == "task_learning"
    assert md["project"] == "p"
    assert md["subagent"] is None


def test_tag_chunk_memory_md_bug_keyword_yields_anti_pattern():
    src = ics.Source(path=Path("/m/MEMORY.md"), source_type="memory_md", project_name="m")
    chunk = ics.Chunk(heading="Bug fix for redis pool", body="...", content_hash="x")
    md = ics.tag_chunk(src, chunk)
    assert md["type"] == "anti_pattern"


def test_tag_chunk_memory_md_decision_keyword_yields_decision():
    src = ics.Source(path=Path("/m/MEMORY.md"), source_type="memory_md", project_name="m")
    chunk = ics.Chunk(heading="We decided to use Postgres", body="...", content_hash="x")
    md = ics.tag_chunk(src, chunk)
    assert md["type"] == "decision"


def test_tag_chunk_memory_md_never_keyword_yields_anti_pattern():
    src = ics.Source(path=Path("/m/MEMORY.md"), source_type="memory_md", project_name="m")
    chunk = ics.Chunk(heading="Critical Rules", body="never do X", content_hash="x")
    md = ics.tag_chunk(src, chunk)
    assert md["type"] == "anti_pattern"


def test_tag_chunk_agent_memory_carries_subagent_name():
    src = ics.Source(
        path=Path("/Users/alice/.claude/agent-memory/meta-reviewer/MEMORY.md"),
        source_type="agent_memory",
        subagent_name="meta-reviewer",
    )
    chunk = ics.Chunk(heading="feedback", body="...", content_hash="x")
    md = ics.tag_chunk(src, chunk)
    assert md["type"] == "task_learning"
    assert md["subagent"] == "meta-reviewer"
    assert md["project"] is None


def test_tag_chunk_claude_local_defaults_to_user_preference():
    src = ics.Source(path=Path("/proj/CLAUDE.local.md"), source_type="claude_local")
    chunk = ics.Chunk(heading="Sandbox", body="...", content_hash="x")
    md = ics.tag_chunk(src, chunk)
    assert md["type"] == "user_preference"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "tag_chunk"`
Expected: 8 FAILs.

- [ ] **Step 3: Implement `Source` + `tag_chunk`**

Add to `mem0-plugin/scripts/import_claude_state.py` (after the `Chunk` dataclass):

```python
SOURCE_TYPES = {
    "claude_md_managed",
    "claude_md_user",
    "claude_md_project",
    "claude_md_import",
    "claude_local",
    "rule",
    "memory_md",
    "memory_topic",
    "agent_memory",
    "agent_memory_topic",
}

DEFAULT_TYPE_BY_SOURCE = {
    "claude_md_managed": "convention",
    "claude_md_user": "convention",
    "claude_md_project": "convention",
    "claude_md_import": "convention",
    "claude_local": "user_preference",
    "rule": "convention",
    "memory_md": "task_learning",
    "memory_topic": "task_learning",
    "agent_memory": "task_learning",
    "agent_memory_topic": "task_learning",
}

# Compiled once. Order matters when multiple match: anti_pattern wins over
# decision wins over user_preference.
_ANTI_PATTERN_RE = re.compile(r"\b(bug|fix|debug|never|always|critical)\b", re.IGNORECASE)
_DECISION_RE = re.compile(r"\b(decision|decided|chose|picked|chosen)\b", re.IGNORECASE)
_PREFERENCE_RE = re.compile(r"\b(prefer|preference|style)\b", re.IGNORECASE)


@dataclass
class Source:
    path: Path
    source_type: str
    project_name: str | None = None
    subagent_name: str | None = None


def _override_type(default: str, search_text: str) -> str:
    if _ANTI_PATTERN_RE.search(search_text):
        return "anti_pattern"
    if _DECISION_RE.search(search_text):
        return "decision"
    if _PREFERENCE_RE.search(search_text):
        return "user_preference"
    return default


def tag_chunk(source: Source, chunk: Chunk) -> dict[str, Any]:
    """Build the metadata dict attached to the chunk's add_memory POST."""
    default = DEFAULT_TYPE_BY_SOURCE.get(source.source_type, "task_learning")
    type_value = _override_type(default, chunk.heading + "\n" + chunk.body)
    return {
        "source_file": str(source.path),
        "source_type": source.source_type,
        "section_heading": chunk.heading,
        "project": source.project_name,
        "subagent": source.subagent_name,
        "content_hash": chunk.content_hash,
        "type": type_value,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "tag_chunk"`
Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): Source dataclass + tag_chunk with keyword type overrides"
```

---

## Task 7: `@import` resolution

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

CLAUDE.md supports `@path` imports recursive to depth 5. We mirror that resolver. Cycles, missing files, and depth overflow all become warnings (not errors) and the offending import is skipped past the first hit.

- [ ] **Step 1: Write the failing tests**

Append:

```python
IMPORT_RE_TEST_BODY = """# Top
Some intro.
@./child.md
And more text. See @~/.claude/CLAUDE.md too.
"""


def test_resolve_imports_relative(tmp_path: Path):
    parent = tmp_path / "CLAUDE.md"
    child = tmp_path / "child.md"
    parent.write_text("Body\n@./child.md\n")
    child.write_text("Child body\n")
    imports = ics.resolve_imports(parent)
    assert child in imports


def test_resolve_imports_absolute(tmp_path: Path):
    parent = tmp_path / "CLAUDE.md"
    other = tmp_path / "other.md"
    parent.write_text(f"Body\n@{other}\n")
    other.write_text("Other body\n")
    assert other in ics.resolve_imports(parent)


def test_resolve_imports_home_expansion(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    home_file = tmp_path / "global.md"
    home_file.write_text("Global body\n")
    parent = tmp_path / "CLAUDE.md"
    parent.write_text("Body\n@~/global.md\n")
    assert home_file in ics.resolve_imports(parent)


def test_resolve_imports_cycle_detection(tmp_path: Path, caplog):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("@./b.md\n")
    b.write_text("@./a.md\n")
    with caplog.at_level("WARNING"):
        imports = ics.resolve_imports(a)
    assert b in imports
    assert a not in imports  # the cycle back to a is skipped
    assert any("cycle" in r.message.lower() for r in caplog.records)


def test_resolve_imports_depth_limit(tmp_path: Path, caplog):
    chain = [tmp_path / f"l{i}.md" for i in range(8)]
    for i in range(7):
        chain[i].write_text(f"@./{chain[i+1].name}\n")
    chain[7].write_text("end\n")
    with caplog.at_level("WARNING"):
        imports = ics.resolve_imports(chain[0])
    # Depth 5 means we get l1..l5 (5 levels deep), but not l6/l7.
    paths = {p.name for p in imports}
    assert "l5.md" in paths
    assert "l6.md" not in paths
    assert any("depth" in r.message.lower() for r in caplog.records)


def test_resolve_imports_missing_target(tmp_path: Path, caplog):
    parent = tmp_path / "CLAUDE.md"
    parent.write_text("@./nonexistent.md\n")
    with caplog.at_level("WARNING"):
        imports = ics.resolve_imports(parent)
    assert imports == []
    assert any("missing" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "resolve_imports"`
Expected: 6 FAILs.

- [ ] **Step 3: Implement `resolve_imports`**

Add to `mem0-plugin/scripts/import_claude_state.py`:

```python
IMPORT_LINE_RE = re.compile(r"(?<![A-Za-z0-9_])@([^\s,;)]+)")
MAX_IMPORT_DEPTH = 5


def _parse_import_paths(text: str, base: Path) -> list[Path]:
    paths: list[Path] = []
    for m in IMPORT_LINE_RE.finditer(text):
        raw = m.group(1)
        if raw.startswith("~"):
            resolved = Path(os.path.expanduser(raw))
        elif raw.startswith("/"):
            resolved = Path(raw)
        else:
            resolved = (base.parent / raw).resolve()
        paths.append(resolved)
    return paths


def resolve_imports(
    path: Path,
    *,
    depth: int = 0,
    visited: set[Path] | None = None,
) -> list[Path]:
    """Return the transitive @-import closure starting at `path`.

    The starting `path` itself is NOT included in the result. Cycles, missing
    targets, and depth overflows are logged and skipped.
    """
    if visited is None:
        visited = set()
    if depth >= MAX_IMPORT_DEPTH:
        log.warning("import depth limit reached at %s (max=%d)", path, MAX_IMPORT_DEPTH)
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    out: list[Path] = []
    for target in _parse_import_paths(text, path):
        try:
            target_resolved = target.resolve()
        except OSError:
            continue
        if target_resolved in visited:
            log.warning("import cycle detected: skipping %s (re-entered from %s)", target_resolved, path)
            continue
        if not target_resolved.exists():
            log.warning("missing import target %s referenced from %s", target_resolved, path)
            continue
        visited.add(target_resolved)
        out.append(target_resolved)
        # Recurse to follow imports inside the imported file too.
        out.extend(
            resolve_imports(target_resolved, depth=depth + 1, visited=visited)
        )
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "resolve_imports"`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): @import resolver with cycle + depth + missing handling"
```

---

## Task 8: File discovery

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

`discover()` walks all known paths and returns a list of `Source` objects. The function takes an explicit `home` and `cwd` for testability.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def _touch(p: Path, content: str = ""):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content or "placeholder\n")


def test_discover_finds_user_and_project_claude_md(tmp_path: Path):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "CLAUDE.md", "user rules\n")
    _touch(cwd / "CLAUDE.md", "project rules\n")
    sources = ics.discover(home=home, cwd=cwd)
    by_type = {s.source_type: s for s in sources}
    assert "claude_md_user" in by_type
    assert "claude_md_project" in by_type


def test_discover_finds_project_memory(tmp_path: Path):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    proj_dir = home / ".claude" / "projects" / "-Users-alice-myproj" / "memory"
    _touch(proj_dir / "MEMORY.md", "memory body\n")
    _touch(proj_dir / "debugging.md", "topic body\n")
    sources = ics.discover(home=home, cwd=cwd)
    types = {s.source_type for s in sources}
    assert "memory_md" in types
    assert "memory_topic" in types
    mem = next(s for s in sources if s.source_type == "memory_md")
    assert mem.project_name == "myproj"  # decoded from the encoded directory


def test_discover_finds_agent_memory(tmp_path: Path):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "agent-memory" / "meta-reviewer" / "MEMORY.md", "x")
    _touch(home / ".claude" / "agent-memory" / "meta-reviewer" / "feedback_style.md", "x")
    sources = ics.discover(home=home, cwd=cwd)
    sub = [s for s in sources if s.source_type.startswith("agent_memory")]
    assert len(sub) == 2
    assert all(s.subagent_name == "meta-reviewer" for s in sub)


def test_discover_picks_up_at_imports(tmp_path: Path):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    main = home / ".claude" / "CLAUDE.md"
    child = home / ".claude" / "extra.md"
    _touch(main, "@./extra.md\n")
    _touch(child, "extra body\n")
    sources = ics.discover(home=home, cwd=cwd)
    types = {s.source_type for s in sources}
    assert "claude_md_user" in types
    assert "claude_md_import" in types
    imp = next(s for s in sources if s.source_type == "claude_md_import")
    assert imp.path == child.resolve()


def test_discover_ignores_missing_paths(tmp_path: Path):
    """Empty home + cwd should produce zero sources, not crash."""
    sources = ics.discover(home=tmp_path / "missing-home", cwd=tmp_path / "missing-cwd")
    assert sources == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "discover"`
Expected: 5 FAILs.

- [ ] **Step 3: Implement `discover`**

Add to `mem0-plugin/scripts/import_claude_state.py`:

```python
PROJECT_DIR_DECODE_RE = re.compile(r"^-Users-[^-]+-(.+)$")


def _decode_project_name(encoded: str) -> str:
    """`-Users-alice-mem0-platform` → `mem0-platform`.

    Claude Code encodes the project directory path with '-' separators.
    The user's home prefix varies; we keep everything after the username.
    """
    m = PROJECT_DIR_DECODE_RE.match(encoded)
    if m:
        return m.group(1)
    return encoded.lstrip("-")


def _collect_claude_md_chain(cwd: Path) -> list[Path]:
    """Walk up from cwd looking for CLAUDE.md / .claude/CLAUDE.md at each level."""
    chain: list[Path] = []
    seen: set[Path] = set()
    current = cwd
    while True:
        for candidate in (current / "CLAUDE.md", current / ".claude" / "CLAUDE.md"):
            try:
                if candidate.exists() and candidate.resolve() not in seen:
                    chain.append(candidate.resolve())
                    seen.add(candidate.resolve())
            except OSError:
                continue
        parent = current.parent
        if parent == current:
            break
        current = parent
    return chain


def discover(*, home: Path | None = None, cwd: Path | None = None) -> list[Source]:
    """Enumerate every Claude state file we know how to import."""
    home = (home or Path.home()).resolve()
    cwd = (cwd or Path.cwd()).resolve()
    sources: list[Source] = []
    seen_paths: set[Path] = set()

    def add(path: Path, source_type: str, **kw):
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in seen_paths or not resolved.exists():
            return
        seen_paths.add(resolved)
        sources.append(Source(path=resolved, source_type=source_type, **kw))

    # User-global CLAUDE.md
    add(home / ".claude" / "CLAUDE.md", "claude_md_user")

    # User-level .claude/rules
    user_rules_dir = home / ".claude" / "rules"
    if user_rules_dir.is_dir():
        for rule in sorted(user_rules_dir.rglob("*.md")):
            add(rule, "rule")

    # Project CLAUDE.md chain
    for path in _collect_claude_md_chain(cwd):
        add(path, "claude_md_project")

    # Project CLAUDE.local.md
    add(cwd / "CLAUDE.local.md", "claude_local")

    # Project-level .claude/rules
    project_rules_dir = cwd / ".claude" / "rules"
    if project_rules_dir.is_dir():
        for rule in sorted(project_rules_dir.rglob("*.md")):
            add(rule, "rule")

    # Auto-memory per project
    projects_root = home / ".claude" / "projects"
    if projects_root.is_dir():
        for proj_dir in sorted(projects_root.iterdir()):
            mem_dir = proj_dir / "memory"
            if not mem_dir.is_dir():
                continue
            proj_name = _decode_project_name(proj_dir.name)
            for md in sorted(mem_dir.glob("*.md")):
                source_type = "memory_md" if md.name == "MEMORY.md" else "memory_topic"
                add(md, source_type, project_name=proj_name)

    # Subagent auto-memory
    agent_root = home / ".claude" / "agent-memory"
    if agent_root.is_dir():
        for sub_dir in sorted(agent_root.iterdir()):
            if not sub_dir.is_dir():
                continue
            for md in sorted(sub_dir.glob("*.md")):
                source_type = "agent_memory" if md.name == "MEMORY.md" else "agent_memory_topic"
                add(md, source_type, subagent_name=sub_dir.name)

    # Follow @imports for every CLAUDE.md / .local.md / rule we found
    snapshot = list(sources)
    for s in snapshot:
        if s.source_type in {
            "claude_md_user",
            "claude_md_project",
            "claude_local",
            "rule",
        }:
            for imp in resolve_imports(s.path):
                add(imp, "claude_md_import")

    return sources
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "discover"`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): discover() enumerates all Claude state surfaces + follows @imports"
```

---

## Task 9: HTTP dispatcher with retry

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

`post_memory` POSTs a single chunk to `https://api.mem0.ai/v1/memories/`. Handles 401 (stop immediately, raise), 429 (one retry after sleep), 5xx (log + return None), network errors (log + return None).

- [ ] **Step 1: Write the failing tests**

Append:

```python
from unittest.mock import MagicMock, patch


@dataclass
class _FakeResponse:
    status: int
    body: bytes = b'{"results":[{"id":"m_xyz","memory":"text","event":"ADD"}]}'

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


def test_post_memory_success_returns_response_payload(monkeypatch):
    fake = _FakeResponse(status=200)
    monkeypatch.setattr(ics.urllib.request, "urlopen", lambda *a, **kw: fake)
    result = ics.post_memory(
        content="body",
        user_id="alice",
        metadata={"source_type": "memory_md"},
        infer=True,
        api_key="key",
    )
    assert result is not None
    assert result["results"][0]["id"] == "m_xyz"


def test_post_memory_401_raises_auth_error(monkeypatch):
    import urllib.error as _err

    def raise_401(*a, **kw):
        raise _err.HTTPError("u", 401, "unauthorized", {}, None)

    monkeypatch.setattr(ics.urllib.request, "urlopen", raise_401)
    with pytest.raises(ics.AuthError):
        ics.post_memory(
            content="body", user_id="alice", metadata={}, infer=True, api_key="key"
        )


def test_post_memory_429_retries_once(monkeypatch):
    import urllib.error as _err

    calls = {"n": 0}

    def maybe_throttle(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _err.HTTPError("u", 429, "rate limited", {}, None)
        return _FakeResponse(status=200)

    monkeypatch.setattr(ics.urllib.request, "urlopen", maybe_throttle)
    monkeypatch.setattr(ics.time, "sleep", lambda _s: None)
    result = ics.post_memory(
        content="body", user_id="alice", metadata={}, infer=True, api_key="key"
    )
    assert calls["n"] == 2
    assert result is not None


def test_post_memory_500_returns_none(monkeypatch):
    import urllib.error as _err

    def raise_500(*a, **kw):
        raise _err.HTTPError("u", 500, "server error", {}, None)

    monkeypatch.setattr(ics.urllib.request, "urlopen", raise_500)
    result = ics.post_memory(
        content="body", user_id="alice", metadata={}, infer=True, api_key="key"
    )
    assert result is None


def test_post_memory_network_error_returns_none(monkeypatch):
    import urllib.error as _err

    def raise_url(*a, **kw):
        raise _err.URLError("no network")

    monkeypatch.setattr(ics.urllib.request, "urlopen", raise_url)
    result = ics.post_memory(
        content="body", user_id="alice", metadata={}, infer=True, api_key="key"
    )
    assert result is None


def test_post_memory_payload_shape(monkeypatch):
    captured = {}

    def capture(req, timeout=15):
        captured["data"] = json.loads(req.data.decode("utf-8"))
        captured["headers"] = dict(req.header_items())
        return _FakeResponse(status=200)

    monkeypatch.setattr(ics.urllib.request, "urlopen", capture)
    ics.post_memory(
        content="hello",
        user_id="alice",
        metadata={"source_type": "claude_md_user", "type": "convention"},
        infer=True,
        api_key="my-key",
    )
    assert captured["data"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["data"]["user_id"] == "alice"
    assert captured["data"]["metadata"]["source_type"] == "claude_md_user"
    assert captured["data"]["infer"] is True
    auth_header = captured["headers"]["Authorization"]
    assert auth_header == "Token my-key"
```

Also add `import pytest` and `from dataclasses import dataclass` to the top of the test file if not already there.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "post_memory"`
Expected: 6 FAILs.

- [ ] **Step 3: Implement `post_memory`**

Add to `mem0-plugin/scripts/import_claude_state.py`:

```python
import time
import urllib.error
import urllib.request

API_URL = "https://api.mem0.ai"
RETRY_SLEEP_SECS = 2.0
REQUEST_TIMEOUT_SECS = 15


class AuthError(RuntimeError):
    """Raised on 401 to stop the import run immediately."""


def post_memory(
    *,
    content: str,
    user_id: str,
    metadata: dict[str, Any],
    infer: bool,
    api_key: str,
) -> dict[str, Any] | None:
    """POST one chunk to /v1/memories/. Returns parsed response or None on
    recoverable failure. Raises AuthError on 401."""
    body = {
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
        "metadata": metadata,
        "infer": infer,
    }
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {api_key}",
    }

    for attempt in (1, 2):
        req = urllib.request.Request(
            f"{API_URL}/v1/memories/",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECS) as resp:
                if resp.status in (200, 201):
                    return json.loads(resp.read().decode("utf-8"))
                log.warning("API returned status %d", resp.status)
                return None
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AuthError("Auth failed — check MEM0_API_KEY") from e
            if e.code == 429 and attempt == 1:
                log.warning("rate limited, sleeping %.1fs and retrying once", RETRY_SLEEP_SECS)
                time.sleep(RETRY_SLEEP_SECS)
                continue
            log.warning("API error %d: %s", e.code, e.reason)
            return None
        except urllib.error.URLError as e:
            log.warning("network error: %s", e)
            return None
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "post_memory"`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): post_memory with 401/429/5xx/network handling + retry"
```

---

## Task 10: Upload orchestrator with per-chunk marker writes

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

`run_import` ties discovery → chunking → tagging → posting → marker. It skips chunks whose `content_hash` is already in the marker (idempotent re-runs). It writes the marker after each successful chunk (resume-on-crash).

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_run_import_uploads_each_chunk_once(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "CLAUDE.md", "## A\n\nbody A\n\n## B\n\nbody B\n")

    marker_path = tmp_path / "marker.json"
    posted: list[dict] = []

    def fake_post(**kw):
        posted.append(kw)
        return {"results": [{"id": f"m_{len(posted)}", "memory": kw["content"], "event": "ADD"}]}

    monkeypatch.setattr(ics, "post_memory", fake_post)

    stats = ics.run_import(
        home=home,
        cwd=cwd,
        marker_path=marker_path,
        user_id="alice",
        api_key="key",
        infer=True,
        dry_run=False,
        source_filter=None,
    )
    assert stats["uploaded"] == 2
    assert stats["skipped"] == 0
    assert stats["failed"] == 0
    marker = ics.read_marker(marker_path)
    assert len(marker["imports"]) == 1
    assert len(marker["imports"][0]["chunks"]) == 2


def test_run_import_skips_already_imported_chunks(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    text = "## A\n\nbody A\n\n## B\n\nbody B\n"
    _touch(home / ".claude" / "CLAUDE.md", text)
    marker_path = tmp_path / "marker.json"

    posted: list[dict] = []
    monkeypatch.setattr(
        ics,
        "post_memory",
        lambda **kw: posted.append(kw) or {"results": [{"id": "m_1", "memory": "", "event": "ADD"}]},
    )
    # First run uploads everything.
    ics.run_import(
        home=home, cwd=cwd, marker_path=marker_path, user_id="alice",
        api_key="key", infer=True, dry_run=False, source_filter=None,
    )
    posted.clear()
    # Second run — same content, no new chunks should upload.
    stats = ics.run_import(
        home=home, cwd=cwd, marker_path=marker_path, user_id="alice",
        api_key="key", infer=True, dry_run=False, source_filter=None,
    )
    assert posted == []
    assert stats["uploaded"] == 0
    assert stats["skipped"] >= 1


def test_run_import_dry_run_makes_no_calls(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "CLAUDE.md", "## A\n\nbody A\n")
    marker_path = tmp_path / "marker.json"

    called = []
    monkeypatch.setattr(ics, "post_memory", lambda **kw: called.append(kw) or None)
    stats = ics.run_import(
        home=home, cwd=cwd, marker_path=marker_path, user_id="alice",
        api_key="key", infer=True, dry_run=True, source_filter=None,
    )
    assert called == []
    assert stats["uploaded"] == 0
    assert stats["planned"] == 1
    assert not marker_path.exists()


def test_run_import_writes_marker_after_each_success(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "CLAUDE.md", "## A\n\nbody A\n\n## B\n\nbody B\n")
    marker_path = tmp_path / "marker.json"

    write_calls: list[int] = []
    real_write = ics.write_marker

    def counting_write(path, marker):
        write_calls.append(len(marker["imports"][0]["chunks"]) if marker["imports"] else 0)
        real_write(path, marker)

    monkeypatch.setattr(ics, "write_marker", counting_write)
    monkeypatch.setattr(
        ics,
        "post_memory",
        lambda **kw: {"results": [{"id": "m", "memory": "", "event": "ADD"}]},
    )
    ics.run_import(
        home=home, cwd=cwd, marker_path=marker_path, user_id="alice",
        api_key="key", infer=True, dry_run=False, source_filter=None,
    )
    # Two chunks => at least two writes that include the growing chunk count.
    assert 1 in write_calls
    assert 2 in write_calls


def test_run_import_partial_failure_resumes(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "CLAUDE.md", "## A\n\nbody A\n\n## B\n\nbody B\n")
    marker_path = tmp_path / "marker.json"

    calls = {"n": 0}

    def half_fail(**kw):
        calls["n"] += 1
        if calls["n"] == 2:
            return None  # second chunk fails
        return {"results": [{"id": f"m_{calls['n']}", "memory": "", "event": "ADD"}]}

    monkeypatch.setattr(ics, "post_memory", half_fail)
    stats1 = ics.run_import(
        home=home, cwd=cwd, marker_path=marker_path, user_id="alice",
        api_key="key", infer=True, dry_run=False, source_filter=None,
    )
    assert stats1["uploaded"] == 1
    assert stats1["failed"] == 1
    # Re-run: the failed chunk should retry (because it was never marked), the
    # succeeded chunk should be skipped.
    monkeypatch.setattr(
        ics,
        "post_memory",
        lambda **kw: {"results": [{"id": "m_2", "memory": "", "event": "ADD"}]},
    )
    stats2 = ics.run_import(
        home=home, cwd=cwd, marker_path=marker_path, user_id="alice",
        api_key="key", infer=True, dry_run=False, source_filter=None,
    )
    assert stats2["uploaded"] == 1
    assert stats2["skipped"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "run_import"`
Expected: 5 FAILs.

- [ ] **Step 3: Implement `run_import`**

Add to `mem0-plugin/scripts/import_claude_state.py`:

```python
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _hash_set_for_file(marker: dict[str, Any], file_path: str) -> set[str]:
    for entry in marker.get("imports", []):
        if entry.get("file") == file_path:
            return {c["content_hash"] for c in entry.get("chunks", [])}
    return set()


def _get_or_create_file_entry(marker: dict[str, Any], file_path: str, source_type: str) -> dict[str, Any]:
    for entry in marker["imports"]:
        if entry.get("file") == file_path:
            return entry
    entry = {
        "file": file_path,
        "source_type": source_type,
        "imported_at": _now_iso(),
        "chunks": [],
    }
    marker["imports"].append(entry)
    return entry


def run_import(
    *,
    home: Path,
    cwd: Path,
    marker_path: Path,
    user_id: str,
    api_key: str,
    infer: bool,
    dry_run: bool,
    source_filter: str | None,
) -> dict[str, int]:
    """Orchestrate the full import. Returns a stats dict.

    Keys: planned, uploaded, skipped, failed, files.
    """
    marker = read_marker(marker_path)
    sources = discover(home=home, cwd=cwd)
    if source_filter:
        sources = [s for s in sources if s.source_type == source_filter]

    stats = {"planned": 0, "uploaded": 0, "skipped": 0, "failed": 0, "files": len(sources)}

    for source in sources:
        try:
            text = source.path.read_text(encoding="utf-8")
        except OSError as e:
            log.warning("cannot read %s: %s", source.path, e)
            continue
        if not text.strip():
            continue
        chunks = chunk_markdown(text)
        already = _hash_set_for_file(marker, str(source.path))

        for chunk in chunks:
            stats["planned"] += 1
            if chunk.content_hash in already:
                stats["skipped"] += 1
                continue
            if dry_run:
                continue
            metadata = tag_chunk(source, chunk)
            try:
                resp = post_memory(
                    content=chunk.body,
                    user_id=user_id,
                    metadata=metadata,
                    infer=infer,
                    api_key=api_key,
                )
            except AuthError:
                log.error("auth failed — aborting import")
                raise
            if resp is None:
                stats["failed"] += 1
                continue
            memory_ids = [item.get("id", "") for item in resp.get("results", [])]
            entry = _get_or_create_file_entry(marker, str(source.path), source.source_type)
            entry["chunks"].append(
                {
                    "heading": chunk.heading,
                    "content_hash": chunk.content_hash,
                    "memory_ids": memory_ids,
                }
            )
            marker["last_run_at"] = _now_iso()
            marker["user_id"] = user_id
            write_marker(marker_path, marker)
            stats["uploaded"] += 1

    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "run_import"`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): run_import orchestrator with per-chunk marker writes + skip-by-hash"
```

---

## Task 11: CLI argparse + `main`

**Files:**
- Modify: `mem0-plugin/scripts/import_claude_state.py`
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

`main` parses flags, resolves user_id via `_identity.resolve_user_id()`, reads `MEM0_API_KEY`, prints a Rich-free human summary, exits 0/1.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_main_missing_api_key_exits_1(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    rc = ics.main(["--dry-run"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "MEM0_API_KEY" in captured.err or "MEM0_API_KEY" in captured.out


def test_main_dry_run_prints_plan(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("MEM0_API_KEY", "key")
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "CLAUDE.md", "## A\n\nbody A\n")
    marker_path = tmp_path / "marker.json"

    monkeypatch.setattr(ics, "_get_home", lambda: home)
    monkeypatch.setattr(ics, "_get_cwd", lambda: cwd)
    monkeypatch.setattr(ics, "MARKER_PATH", marker_path)

    rc = ics.main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Would upload" in out or "planned" in out.lower()
    assert not marker_path.exists()


def test_main_reset_wipes_marker_before_running(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "key")
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "CLAUDE.md", "## A\n\nbody A\n")
    marker_path = tmp_path / "marker.json"
    ics.write_marker(marker_path, {"schema_version": 1, "imports": [{"file": "stale", "chunks": []}]})

    monkeypatch.setattr(ics, "_get_home", lambda: home)
    monkeypatch.setattr(ics, "_get_cwd", lambda: cwd)
    monkeypatch.setattr(ics, "MARKER_PATH", marker_path)
    monkeypatch.setattr(
        ics,
        "post_memory",
        lambda **kw: {"results": [{"id": "m", "memory": "", "event": "ADD"}]},
    )

    rc = ics.main(["--reset"])
    assert rc == 0
    marker = ics.read_marker(marker_path)
    files = [e["file"] for e in marker["imports"]]
    assert "stale" not in files


def test_main_no_infer_flag_propagates(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "key")
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    _touch(home / ".claude" / "CLAUDE.md", "## A\n\nbody A\n")
    marker_path = tmp_path / "marker.json"
    monkeypatch.setattr(ics, "_get_home", lambda: home)
    monkeypatch.setattr(ics, "_get_cwd", lambda: cwd)
    monkeypatch.setattr(ics, "MARKER_PATH", marker_path)

    captured: list[bool] = []
    monkeypatch.setattr(
        ics,
        "post_memory",
        lambda **kw: captured.append(kw["infer"]) or {"results": [{"id": "m", "memory": "", "event": "ADD"}]},
    )
    rc = ics.main(["--no-infer"])
    assert rc == 0
    assert captured and captured[0] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "main_"`
Expected: 4 FAILs.

- [ ] **Step 3: Implement `main` (replace the existing stub)**

Replace the existing `main` in `mem0-plugin/scripts/import_claude_state.py` with:

```python
import argparse


def _get_home() -> Path:
    return Path.home()


def _get_cwd() -> Path:
    return Path.cwd()


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="import_claude_state.py",
        description="Holistic import of on-disk Claude state into mem0.",
    )
    p.add_argument("--dry-run", action="store_true", help="Print plan, don't upload.")
    p.add_argument("--reset", action="store_true", help="Delete marker before running.")
    p.add_argument("--no-infer", action="store_true", help="Upload with infer=False.")
    p.add_argument(
        "--source",
        choices=sorted(SOURCE_TYPES),
        default=None,
        help="Restrict to one source_type.",
    )
    return p


def _print_summary(stats: dict[str, int], *, dry_run: bool) -> None:
    if dry_run:
        print(
            f"[dry-run] Would upload {stats['planned'] - stats['skipped']} chunks from {stats['files']} files "
            f"({stats['skipped']} already imported, planned={stats['planned']})."
        )
        return
    print(
        f"Imported {stats['uploaded']} chunks from {stats['files']} files "
        f"(skipped {stats['skipped']}, failed {stats['failed']})."
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    api_key = os.environ.get("MEM0_API_KEY", "")
    if not api_key:
        print("MEM0_API_KEY not set — see plugin README.", file=sys.stderr)
        return 1

    try:
        from _identity import resolve_user_id  # type: ignore[import-not-found]
    except ImportError:
        # Fall back to env / USER if _identity isn't importable (e.g. tests).
        def resolve_user_id() -> str:
            return os.environ.get("MEM0_USER_ID") or os.environ.get("USER") or "default"

    user_id = resolve_user_id()

    if args.reset:
        try:
            MARKER_PATH.unlink()
        except FileNotFoundError:
            pass

    try:
        stats = run_import(
            home=_get_home(),
            cwd=_get_cwd(),
            marker_path=MARKER_PATH,
            user_id=user_id,
            api_key=api_key,
            infer=not args.no_infer,
            dry_run=args.dry_run,
            source_filter=args.source,
        )
    except AuthError as e:
        print(str(e), file=sys.stderr)
        return 1

    _print_summary(stats, dry_run=args.dry_run)
    return 0
```

Confirm `_identity.py` exposes a `resolve_user_id()` callable — it does (the existing `on_pre_compact.py` imports it). If not, the fallback above keeps tests green.

Also: tests use `--reset` against a `tmp_path` marker. The `if args.reset: MARKER_PATH.unlink()` block uses the module-level `MARKER_PATH`, which tests monkeypatch. Good.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v -k "main_"`
Expected: `4 passed`. Also run the full file:

`pytest tests/plugin_scripts/test_import_claude_state.py -v`
Expected: all tests so far pass (~40 tests).

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/test_import_claude_state.py
git commit -m "feat(plugin): import_claude_state CLI with --dry-run / --reset / --no-infer / --source"
```

---

## Task 12: End-to-end integration test

**Files:**
- Modify: `tests/plugin_scripts/test_import_claude_state.py`

One realistic fixture exercising every source type. Confirms discovery → chunking → tagging → posting → marker shape all align.

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_end_to_end_full_fixture(tmp_path: Path, monkeypatch):
    """Realistic fixture covering CLAUDE.md + @import + MEMORY.md + agent-memory.

    Asserts: all four files discovered, chunks produced, POSTs made with the
    right metadata, marker reflects every successful chunk.
    """
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"

    # User CLAUDE.md with an @import
    _touch(
        home / ".claude" / "CLAUDE.md",
        "# Global\n\n## Coding Style\n\nUse 2 spaces.\n\n## More\n\n@./extra.md\n",
    )
    _touch(home / ".claude" / "extra.md", "## Extra Rule\n\nNever push to main.\n")

    # Project CLAUDE.local.md
    _touch(cwd / "CLAUDE.local.md", "## Sandbox\n\nLocal API URL: http://localhost:8000\n")

    # Project auto-memory
    proj_mem = home / ".claude" / "projects" / "-Users-alice-myproj" / "memory"
    _touch(
        proj_mem / "MEMORY.md",
        "## Critical Rules\n\nNever touch prod.\n\n## Build\n\nrun make test.\n",
    )
    _touch(proj_mem / "graph-details.md", "## Decision\n\nWe decided to use HNSW.\n")

    # Agent memory
    agent_dir = home / ".claude" / "agent-memory" / "meta-reviewer"
    _touch(agent_dir / "MEMORY.md", "## Style\n\nPrefer concise reviews.\n")
    _touch(agent_dir / "feedback_redis.md", "## Bug fix\n\nDebug the redis pool leak.\n")

    marker_path = tmp_path / "marker.json"

    posted: list[dict] = []

    def fake_post(**kw):
        posted.append(kw)
        return {"results": [{"id": f"m_{len(posted)}", "memory": kw["content"], "event": "ADD"}]}

    monkeypatch.setattr(ics, "post_memory", fake_post)

    stats = ics.run_import(
        home=home,
        cwd=cwd,
        marker_path=marker_path,
        user_id="alice",
        api_key="key",
        infer=True,
        dry_run=False,
        source_filter=None,
    )

    # Discovery covered: user CLAUDE.md, @import, CLAUDE.local.md, memory_md,
    # memory_topic, agent_memory, agent_memory_topic = 7 files.
    assert stats["files"] == 7
    assert stats["uploaded"] == len(posted)
    assert stats["failed"] == 0

    # Metadata correctness — pick one example of each source_type and verify.
    metas = [p["metadata"] for p in posted]
    types_seen = {m["source_type"] for m in metas}
    assert {
        "claude_md_user",
        "claude_md_import",
        "claude_local",
        "memory_md",
        "memory_topic",
        "agent_memory",
        "agent_memory_topic",
    } <= types_seen

    # Keyword overrides hit where expected:
    decision_metas = [m for m in metas if m["type"] == "decision"]
    assert any("graph-details.md" in m["source_file"] for m in decision_metas)

    anti_pattern_metas = [m for m in metas if m["type"] == "anti_pattern"]
    assert any(
        "Critical" in m["section_heading"] or "Bug" in m["section_heading"]
        for m in anti_pattern_metas
    )

    # Marker shape: one entry per file actually uploaded.
    marker = ics.read_marker(marker_path)
    files_in_marker = {e["file"] for e in marker["imports"]}
    assert len(files_in_marker) == 7
    total_chunks_in_marker = sum(len(e["chunks"]) for e in marker["imports"])
    assert total_chunks_in_marker == stats["uploaded"]
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py::test_end_to_end_full_fixture -v`
Expected: PASS if all prior tasks are wired correctly. If not, debug whichever assertion fails — the test is a smoke-check of every prior task.

- [ ] **Step 3: (No implementation step — this task is purely a regression net)**

If the test fails, identify which unit was wrong and add a focused unit test for that specific gap, then fix it. Do not patch the integration test to make it pass.

- [ ] **Step 4: Run the whole test file**

Run: `pytest tests/plugin_scripts/test_import_claude_state.py -v`
Expected: all tests pass (~41 tests).

- [ ] **Step 5: Commit**

```bash
git add tests/plugin_scripts/test_import_claude_state.py
git commit -m "test(plugin): end-to-end fixture covering every Claude state source type"
```

---

## Task 13: Extend `on_session_start.sh` with the nudge block

**Files:**
- Modify: `mem0-plugin/scripts/on_session_start.sh`

Add a new conditional block AFTER the existing identity + bootstrap output. The block emits a holistic-import nudge ONLY if the marker file doesn't exist. Match the existing script's style (heredoc, no `set -e` to avoid aborting on shell quirks).

- [ ] **Step 1: Read the existing script to find the insertion point**

Run: `cat mem0-plugin/scripts/on_session_start.sh`

Note where the existing `if [ "$SOURCE" = "startup" ]; then … elif … elif … fi` block ends. The new block goes AFTER that whole `if/elif` chain but BEFORE the trailing `exit 0`.

- [ ] **Step 2: Add the new conditional block**

Open `mem0-plugin/scripts/on_session_start.sh` and add, immediately before the final `exit 0`:

```bash
# ── Holistic import nudge ────────────────────────────────────────────────
# One-time nudge to backfill existing CLAUDE.md / MEMORY.md / agent-memory
# into mem0. Silent after the marker file appears (i.e., after first run).
MEM0_IMPORT_MARKER="$HOME/.mem0/imports/claude-state.json"
if [ ! -f "$MEM0_IMPORT_MARKER" ]; then
  cat <<EOF

## Holistic import available

On-disk Claude state (CLAUDE.md, ~/.claude/projects/*/memory, ~/.claude/agent-memory)
has never been imported into mem0. To preview what would be imported, run:

  python3 "$SCRIPT_DIR/import_claude_state.py" --dry-run

Then drop \`--dry-run\` to import. This nudge disappears after the first
successful run. Pass \`--reset\` to re-import from scratch.
EOF
fi
```

The `$SCRIPT_DIR` variable is already set near the top of the script (`SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`).

- [ ] **Step 3: Manual smoke test**

```bash
# Simulate startup with no marker → expect the new block in output.
echo '{"source":"startup"}' | bash mem0-plugin/scripts/on_session_start.sh
```

Expected output should include:
- Identity line (existing)
- Bootstrap rubric (existing)
- `## Holistic import available` (new)

```bash
# Simulate startup WITH a marker → expect the new block to be silent.
mkdir -p ~/.mem0/imports
echo '{"schema_version":1,"imports":[]}' > ~/.mem0/imports/claude-state.json
echo '{"source":"startup"}' | bash mem0-plugin/scripts/on_session_start.sh
rm ~/.mem0/imports/claude-state.json
```

Expected output should include the identity + bootstrap but NOT the holistic-import block.

- [ ] **Step 4: Run the Python tests to confirm nothing broke**

Run: `pytest tests/plugin_scripts/ -v`
Expected: all tests still pass.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/on_session_start.sh
git commit -m "feat(plugin): SessionStart hook nudges agent when on-disk Claude state is un-imported"
```

---

## Task 14: README + plugin version bump

**Files:**
- Modify: `mem0-plugin/README.md`
- Modify: `mem0-plugin/.claude-plugin/plugin.json`
- Modify: `mem0-plugin/CHANGELOG.md`

Add a "Holistic import" section to the README that documents what the script does, how to run it, and the `--dry-run` / `--reset` / `--no-infer` / `--source` flags. Bump the plugin version. Add a CHANGELOG entry.

- [ ] **Step 1: Add a section to `mem0-plugin/README.md`**

Open `mem0-plugin/README.md` and add this section AFTER the existing "Optional: tune categories for coding workflows" section (so it appears alongside other "extras"):

```markdown
## Optional: holistic import of existing Claude state

If you've been using Claude Code before installing mem0, you have on-disk
state (CLAUDE.md files, `~/.claude/projects/*/memory/`, `~/.claude/agent-memory/*`)
that won't appear in mem0 until you backfill it. A one-shot importer ships
with the plugin:

```bash
# Preview what would be imported:
python3 mem0-plugin/scripts/import_claude_state.py --dry-run

# Run the import:
python3 mem0-plugin/scripts/import_claude_state.py
```

What it does:

- Discovers every `CLAUDE.md` (user / project / nested), `@import` target,
  `.claude/rules/*.md`, `~/.claude/projects/*/memory/*.md`, and
  `~/.claude/agent-memory/*/*.md` on your machine.
- Heading-chunks each file (H2 default, descending to H3 for oversize
  sections, merging tiny siblings). Code-fenced blocks are preserved.
- POSTs each chunk to mem0 with metadata: `source_file`, `source_type`,
  `section_heading`, `project`, `subagent`, `content_hash`, and a `type`
  matching the `mem0-mcp` skill vocabulary (`convention`, `user_preference`,
  `task_learning`, `anti_pattern`, `decision`).
- Writes `~/.mem0/imports/claude-state.json` to remember what's been
  uploaded. Re-running is idempotent: only new chunks are sent.

Flags:

| Flag | Meaning |
|---|---|
| `--dry-run` | Print the import plan; don't upload. |
| `--reset` | Wipe the marker before running (forces full re-import). |
| `--no-infer` | Upload chunks raw (`infer=False`). Default is `infer=True` so mem0 extracts atomic facts. |
| `--source <type>` | Restrict to one source type (e.g., `--source memory_md`). |

The SessionStart hook nudges you about this one-shot importer the first
time you open a session after installing. Once you run it (or once the
marker file exists), the nudge disappears.
```

- [ ] **Step 2: Bump the plugin version**

Edit `mem0-plugin/.claude-plugin/plugin.json`:

```json
{
  "name": "mem0",
  "version": "0.2.0",
  "description": "Mem0 memory layer for AI applications. Add persistent memory, personalization, and semantic search to Claude workflows using the Mem0 Platform MCP server.",
  "author": {
    "name": "Mem0",
    "email": "support@mem0.ai"
  },
  "homepage": "https://mem0.ai",
  "repository": "https://github.com/mem0ai/mem0",
  "license": "Apache-2.0",
  "keywords": ["memory", "personalization", "mcp", "semantic-search"]
}
```

(Version bump from `0.1.3` to `0.2.0` because this is a feature, not a patch.)

- [ ] **Step 3: Add CHANGELOG entry**

Open `mem0-plugin/CHANGELOG.md`. Find the top of the file (most recent entries first) and add the new entry at the top:

```markdown
## 0.2.0

### Added
- Holistic import: a one-shot `import_claude_state.py` script backfills
  existing CLAUDE.md / @imports / `.claude/rules` / project auto-memory /
  subagent memory into mem0 with heading-based chunking, metadata tagging,
  and content-hash-based idempotent re-runs. SessionStart hook nudges
  agents to run it on first session after install.
```

(Keep the existing entries below unchanged.)

- [ ] **Step 4: Smoke-test the new help output**

Run: `python3 mem0-plugin/scripts/import_claude_state.py --help`
Expected: help text listing `--dry-run`, `--reset`, `--no-infer`, `--source` with valid choices.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/README.md mem0-plugin/.claude-plugin/plugin.json mem0-plugin/CHANGELOG.md
git commit -m "docs(plugin): document holistic import + bump plugin version to 0.2.0"
```

---

## Final verification

Run the full test suite once more to confirm nothing regressed:

```bash
pytest tests/plugin_scripts/ -v
```

Expected: all tests pass.

Run `ruff check` to confirm the new script follows project linting:

```bash
ruff check mem0-plugin/scripts/import_claude_state.py
```

Expected: no errors. If ruff finds issues, fix them and amend the last commit that introduced them.

Look at the commits with `git log --oneline -14` — expect the 14 task commits to be small, focused, and conventionally named (`feat(plugin):` / `test(plugin):` / `docs(plugin):`).

---

## Plan self-review

**Spec coverage:**
- §4 Architecture (script + hook block + marker) → Tasks 1, 10, 11, 13.
- §5 Components: discover (Task 8), resolve_imports (Task 7), chunk_markdown (Tasks 3-5), tag_chunk (Task 6), upload/run_import (Task 10), post_memory (Task 9), marker I/O (Task 2), main (Task 11). ✅
- §6 Data flow: covered by integration test (Task 12) + manual hook smoke (Task 13).
- §7 Error handling: AuthError (Task 9, 11), 429 retry (Task 9), 5xx + network skip (Task 9), corrupted marker (Task 2), missing API key (Task 11), partial-failure resume (Task 10), code-fence safety (Task 5), import cycle / depth / missing (Task 7).
- §8 Testing: every named test case from spec is implemented (chunker ≥9 cases, tag_chunk 8, resolve_imports 6, marker I/O 4, integration covers full fixture + reset + no-infer + resume).
- §9 File layout: matches exactly.

**Placeholder scan:** No "TBD", no "implement later", no "fill in details". Every code step contains the actual code.

**Type consistency:**
- `Source` dataclass defined in Task 6, used in Tasks 7, 8, 10. Fields: `path`, `source_type`, `project_name`, `subagent_name` — consistent.
- `Chunk` dataclass defined in Task 3, used in Tasks 4, 5, 6, 10. Fields: `heading`, `body`, `content_hash` — consistent.
- `read_marker` returns `dict[str, Any]`, used in `run_import` (Task 10) and `main` (Task 11). Shape matches the spec's marker schema.
- `post_memory` signature uses keyword-only args (`content`, `user_id`, `metadata`, `infer`, `api_key`) — `run_import` calls it with exactly those keywords.
- `AuthError` defined in Task 9, raised in `run_import` (Task 10), caught in `main` (Task 11).
- Module-level `MARKER_PATH` defined in Task 2, monkeypatched in Task 11 tests, used in `main` for `--reset`.

**Scope check:** Single feature, one new script + one hook block + one marker file. Independently testable. Implementation plan is internally complete; no decisions deferred to runtime.
