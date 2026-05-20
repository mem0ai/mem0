# Claude State Holistic Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Handoff note:** This plan was written as the next-step from the design spec but the implementation was never executed because the original owner left. It remains accurate as a blueprint. Anyone picking this up should treat the tasks as a recommended ordering — the testing steps assume TDD, but the design itself does not require it. If you prefer to implement the script first and add tests after, the dependency order between tasks 2 → 10 (data structures → orchestrator) still holds.

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

Create `tests/plugin_scripts/__init__.py` as an empty file.

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

`pytest tests/plugin_scripts/test_import_claude_state.py -v`
Expected: FAIL with `ModuleNotFoundError`.

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

```bash
chmod +x mem0-plugin/scripts/import_claude_state.py
```

- [ ] **Step 4: Verify the smoke test passes**

`pytest tests/plugin_scripts/test_import_claude_state.py -v`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add mem0-plugin/scripts/import_claude_state.py tests/plugin_scripts/
git commit -m "feat(plugin): scaffold import_claude_state.py + test harness"
```

---

## Task 2: Marker file I/O

**Files:** `mem0-plugin/scripts/import_claude_state.py`, `tests/plugin_scripts/test_import_claude_state.py`

Marker reads must tolerate missing files and corrupted JSON (returning an empty marker so the run continues). Writes are atomic (temp file + rename).

- [ ] **Step 1: Write the failing tests** — see code in spec §5 (Marker I/O) for the schema. Tests: `test_read_marker_missing_returns_empty`, `test_read_marker_corrupted_returns_empty`, `test_write_marker_then_read_roundtrip`, `test_write_marker_is_atomic` (asserts `os.replace` was called with a `.tmp` path).

- [ ] **Step 2: Run tests, verify they fail** — 4 FAILs (AttributeError).

- [ ] **Step 3: Implement** — add to the script (after logging setup, before `main`):

```python
import json
import tempfile
from pathlib import Path
from typing import Any

MARKER_PATH = Path.home() / ".mem0" / "imports" / "claude-state.json"
EMPTY_MARKER: dict[str, Any] = {"schema_version": 1, "imports": []}


def read_marker(path: Path) -> dict[str, Any]:
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

- [ ] **Step 4: Verify tests pass** — `pytest ... -k "marker"`. Expected: 4 passed.
- [ ] **Step 5: Commit** — `feat(plugin): marker file I/O for claude-state import (atomic write, corruption-tolerant read)`

---

## Task 3: Markdown chunker — basic splits

Split at H2 by default. Each chunk gets SHA-256 content hash. Edge cases: no headings (one chunk), only H1 (one chunk with H1 as heading).

Implement `Chunk` dataclass and `chunk_markdown(text) -> list[Chunk]` using `re.MULTILINE` patterns for `^# `, `^## `. Return one chunk per H2 section. Content before the first H2 attaches to the H1 (if any) as a separate chunk. Body always includes the heading line so re-rendering matches the source. `content_hash = sha256(body.strip("\n"))`.

Tests: `test_chunk_markdown_no_headings_returns_one_chunk`, `test_chunk_markdown_only_h1_returns_one_chunk`, `test_chunk_markdown_splits_on_h2`, `test_chunk_markdown_content_hash_deterministic`.

Commit: `feat(plugin): chunk_markdown basic H2 splits + content_hash`.

---

## Task 4: Chunker — descend to H3 on oversize, merge small siblings

Constants: `MAX_CHARS_PER_CHUNK = 2000`, `MIN_CHARS_PER_CHUNK = 200`.

Logic:
1. Split at H2.
2. For each section > MAX, re-split at H3 (if any H3s exist; otherwise emit oversized chunk as-is rather than mid-paragraph break).
3. For adjacent sections where the *first* sibling's stripped body < MIN AND combined size ≤ MAX, merge into the prior chunk. First sibling's heading is preserved.

Tests: `test_chunk_markdown_oversize_h2_descends_to_h3`, `test_chunk_markdown_merges_small_siblings`, `test_chunk_markdown_does_not_merge_below_min_when_already_at_h3`.

Commit: `feat(plugin): chunk_markdown descends to H3 on oversize, merges small siblings`.

---

## Task 5: Chunker — protect code fences from being split

A fenced code block (``` or ~~~) that contains `## ` text must not trigger a split. Add a pre-pass (`_mask_fences`) that walks the text line-by-line tracking open/close fence state and replaces the leading `#` of any heading-like line *inside a fence* with a space (preserving offsets so chunk offsets stay aligned with the original text).

Important invariant: `len(masked) == len(text)`. After splitting on the masked text, slice chunk bodies from the *original* text using the same offsets.

Tests: `test_chunk_markdown_does_not_split_inside_code_fence`, `test_chunk_markdown_handles_nested_fences_with_tilde`.

Commit: `feat(plugin): chunk_markdown protects code-fenced ## from splitting`.

---

## Task 6: Source typing + tagger

Define:

```python
SOURCE_TYPES = {
    "claude_md_managed", "claude_md_user", "claude_md_project", "claude_md_import",
    "claude_local", "rule",
    "memory_md", "memory_topic",
    "agent_memory", "agent_memory_topic",
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

@dataclass
class Source:
    path: Path
    source_type: str
    project_name: str | None = None
    subagent_name: str | None = None
```

Keyword regexes (case-insensitive):
- `_ANTI_PATTERN_RE = \b(bug|fix|debug|never|always|critical)\b`
- `_DECISION_RE = \b(decision|decided|chose|picked|chosen)\b`
- `_PREFERENCE_RE = \b(prefer|preference|style)\b`

Override priority (when multiple match): anti_pattern → decision → user_preference → default. Search heading + body, but heading matches are stronger signal in practice.

`tag_chunk(source, chunk)` returns the metadata dict with `source_file`, `source_type`, `section_heading`, `project`, `subagent`, `content_hash`, `type`.

Tests: 8 cases covering each default + each override path. See spec §5 (Tagging) for the full table.

Commit: `feat(plugin): Source dataclass + tag_chunk with keyword type overrides`.

---

## Task 7: `@import` resolver

Implement `resolve_imports(path, *, depth=0, visited=None) -> list[Path]`:

- Regex: `IMPORT_LINE_RE = r"(?<![A-Za-z0-9_])@([^\s,;)]+)"` (matches `@path` not preceded by a word character, so emails don't trigger).
- `~/` expanded via `os.path.expanduser`.
- Relative paths resolved relative to the importing file's parent.
- Cycle detection via shared `visited` set.
- `MAX_IMPORT_DEPTH = 5`. Log warning on overflow, return `[]`.
- Missing target → warning log, skip.
- The starting `path` is NOT in the result; only descendants are.

Tests: relative, absolute, `~/` expansion, cycle detection, depth limit (chain l0→l7 with depth 5 returns up to l5), missing target.

Commit: `feat(plugin): @import resolver with cycle + depth + missing handling`.

---

## Task 8: File discovery

Implement `discover(*, home=None, cwd=None) -> list[Source]`:

1. User-global CLAUDE.md (`~/.claude/CLAUDE.md`)
2. User-level rules (`~/.claude/rules/**/*.md`)
3. Project CLAUDE.md chain (walking up from `cwd`, checking both `<dir>/CLAUDE.md` and `<dir>/.claude/CLAUDE.md`)
4. Project `CLAUDE.local.md`
5. Project rules (`<cwd>/.claude/rules/**/*.md`)
6. Per-project auto-memory (`~/.claude/projects/*/memory/*.md`, with `MEMORY.md` tagged `memory_md` and others `memory_topic`)
7. Subagent memory (`~/.claude/agent-memory/*/*.md`, with `MEMORY.md` tagged `agent_memory` and others `agent_memory_topic`)
8. Finally, follow `@imports` from every discovered CLAUDE.md / local / rule, adding them as `claude_md_import`

Decode project name from the encoded path (`-Users-alice-mem0-platform` → `mem0-platform`). Use `PROJECT_DIR_DECODE_RE = r"^-Users-[^-]+-(.+)$"` — strips the `-Users-<username>-` prefix.

Use `Path.resolve()` and a `seen_paths` set to dedupe (the same file can be reached by multiple paths via symlinks or hierarchy + import).

Tests: user + project CLAUDE.md, project memory + topic files, agent memory + subagent name, @import pickup, missing-paths → empty list.

Commit: `feat(plugin): discover() enumerates all Claude state surfaces + follows @imports`.

---

## Task 9: HTTP dispatcher with retry

Implement `post_memory(*, content, user_id, metadata, infer, api_key) -> dict | None`:

- POST to `https://api.mem0.ai/v1/memories/` with body `{"messages": [{"role": "user", "content": content}], "user_id": user_id, "metadata": metadata, "infer": infer}`.
- Header: `Authorization: Token {api_key}`, `Content-Type: application/json`.
- Timeout: 15 s.
- 200/201 → return parsed JSON.
- 401 → raise `AuthError` (defined in this module). Caller stops the whole run.
- 429 → log, `time.sleep(2)`, retry once. Second 429 → log + return None.
- Other HTTPError → log + return None.
- URLError (network) → log + return None.

Tests: success path returns payload, 401 raises AuthError, 429 retries once and succeeds, 500 returns None, URLError returns None, payload-shape test asserts the JSON body + Authorization header are exactly right.

Commit: `feat(plugin): post_memory with 401/429/5xx/network handling + retry`.

---

## Task 10: Upload orchestrator with per-chunk marker writes

Implement `run_import(*, home, cwd, marker_path, user_id, api_key, infer, dry_run, source_filter) -> dict[str, int]`:

Stats dict keys: `planned`, `uploaded`, `skipped`, `failed`, `files`.

Algorithm:

```
marker = read_marker(marker_path)
sources = discover(home=home, cwd=cwd)
if source_filter:
    sources = [s for s in sources if s.source_type == source_filter]
stats = {"planned": 0, "uploaded": 0, "skipped": 0, "failed": 0, "files": len(sources)}

for source in sources:
    text = source.path.read_text()  # skip on OSError
    if not text.strip(): continue
    chunks = chunk_markdown(text)
    already_hashes = {c["content_hash"] for c in marker_entry_for(source.path).get("chunks", [])}
    for chunk in chunks:
        stats["planned"] += 1
        if chunk.content_hash in already_hashes:
            stats["skipped"] += 1
            continue
        if dry_run:
            continue
        metadata = tag_chunk(source, chunk)
        try:
            resp = post_memory(content=chunk.body, user_id=user_id, metadata=metadata, infer=infer, api_key=api_key)
        except AuthError:
            raise  # propagate to main, which prints + exits 1
        if resp is None:
            stats["failed"] += 1
            continue
        memory_ids = [item.get("id", "") for item in resp.get("results", [])]
        entry = _get_or_create_file_entry(marker, str(source.path), source.source_type)
        entry["chunks"].append({"heading": chunk.heading, "content_hash": chunk.content_hash, "memory_ids": memory_ids})
        marker["last_run_at"] = _now_iso()
        marker["user_id"] = user_id
        write_marker(marker_path, marker)  # per-chunk! resume-on-crash safety
        stats["uploaded"] += 1
return stats
```

Tests: every chunk uploaded once, already-imported chunks skipped on re-run, dry-run makes no POSTs and writes no marker, marker grows monotonically per chunk (assert write_marker called with growing chunk counts), partial-failure leaves succeeded chunks marked and fails to be retried on next run.

Commit: `feat(plugin): run_import orchestrator with per-chunk marker writes + skip-by-hash`.

---

## Task 11: CLI argparse + `main`

Flags: `--dry-run`, `--reset`, `--no-infer`, `--source <type>` (choices: `sorted(SOURCE_TYPES)`).

`main(argv=None) -> int`:
1. Parse args.
2. Check `MEM0_API_KEY` env. If missing, print to stderr, return 1.
3. Resolve `user_id` via `from _identity import resolve_user_id`. Fallback to `$USER` if import fails (so tests pass without _identity).
4. If `--reset`, `MARKER_PATH.unlink(missing_ok=True)`.
5. Wrap `run_import(...)` in try/except AuthError → print + return 1.
6. Print human summary (dry-run: "Would upload X chunks from Y files...", real: "Imported X chunks from Y files (skipped Z, failed W).").
7. Return 0.

Define module-level helpers `_get_home() -> Path.home()` and `_get_cwd() -> Path.cwd()` so tests can monkeypatch them.

Tests: missing API key → return 1, dry-run prints plan + no marker file, `--reset` wipes pre-existing marker, `--no-infer` sets `infer=False` in the post.

Commit: `feat(plugin): import_claude_state CLI with --dry-run / --reset / --no-infer / --source`.

---

## Task 12: End-to-end integration test

One fixture tmp_path with:
- `~/.claude/CLAUDE.md` containing `@./extra.md`
- `~/.claude/extra.md` (the @import target)
- `<cwd>/CLAUDE.local.md`
- `~/.claude/projects/-Users-alice-myproj/memory/MEMORY.md`
- `~/.claude/projects/-Users-alice-myproj/memory/graph-details.md`
- `~/.claude/agent-memory/meta-reviewer/MEMORY.md`
- `~/.claude/agent-memory/meta-reviewer/feedback_redis.md`

Mock `post_memory`. Call `run_import(...)`. Assert:
- 7 files discovered
- `uploaded == len(posted_calls)`
- All 7 source_types appear in metadata
- Heading keyword overrides hit where expected (e.g., "We decided" → `decision`, "Critical Rules" / "Bug fix" → `anti_pattern`)
- Marker has 7 file entries, total chunk count matches `stats["uploaded"]`

Commit: `test(plugin): end-to-end fixture covering every Claude state source type`.

---

## Task 13: Extend `on_session_start.sh` with the nudge block

Add immediately before the trailing `exit 0`:

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

  python3 "\$SCRIPT_DIR/import_claude_state.py" --dry-run

Then drop \`--dry-run\` to import. This nudge disappears after the first
successful run. Pass \`--reset\` to re-import from scratch.
EOF
fi
```

The `$SCRIPT_DIR` variable is already set near the top of the script via `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`.

Manual smoke: pipe a fake startup JSON to the script with and without the marker file present, confirm the new block appears / disappears.

Commit: `feat(plugin): SessionStart hook nudges agent when on-disk Claude state is un-imported`.

---

## Task 14: README + plugin version bump

- Add a "Holistic import" section to `mem0-plugin/README.md` after the existing "tune categories for coding workflows" section. Document the flags.
- Bump `mem0-plugin/.claude-plugin/plugin.json` version (0.1.3 → 0.2.0 for a feature release).
- Add a CHANGELOG entry at the top of `mem0-plugin/CHANGELOG.md`.

Commit: `docs(plugin): document holistic import + bump plugin version to 0.2.0`.

---

## Final verification

```bash
pytest tests/plugin_scripts/ -v          # all tests pass
ruff check mem0-plugin/scripts/import_claude_state.py  # no lint errors
git log --oneline -14                    # 14 focused commits, conventionally named
```

Manual smoke against a real mem0 account:
```bash
export MEM0_USER_ID="mem0_import_smoke_$(date +%Y%m%d)"
python3 mem0-plugin/scripts/import_claude_state.py --dry-run
python3 mem0-plugin/scripts/import_claude_state.py
# Verify chunks appear in https://app.mem0.ai/dashboard with the right metadata.
```

---

## Plan self-review

**Spec coverage:**
- §4 Architecture → Tasks 1, 10, 11, 13
- §5 Components: discover (Task 8), resolve_imports (Task 7), chunk_markdown (Tasks 3-5), tag_chunk (Task 6), upload/run_import (Task 10), post_memory (Task 9), marker I/O (Task 2), main (Task 11)
- §6 Data flow: integration test (Task 12) + manual hook smoke (Task 13)
- §7 Error handling: AuthError (Task 9, 11), 429 retry (Task 9), 5xx + network skip (Task 9), corrupted marker (Task 2), missing API key (Task 11), partial-failure resume (Task 10), code-fence safety (Task 5), import cycle / depth / missing (Task 7)
- §8 Testing: every named case implemented
- §9 File layout: matches exactly

**Type consistency:**
- `Source` (Task 6) used in Tasks 7, 8, 10. Fields stable.
- `Chunk` (Task 3) used in Tasks 4, 5, 6, 10. Fields stable.
- `read_marker` shape matches spec §5.
- `post_memory` keyword-only args match `run_import` call site.
- `AuthError` defined Task 9, raised Task 10, caught Task 11.
- `MARKER_PATH` defined Task 2, monkeypatched Task 11 tests, used Task 11 main.

**Scope:** Single feature, one new script + one hook block + one marker file. No deferred decisions.
