# Claude state holistic import for `mem0-plugin`

**Status:** draft (awaiting user review)
**Date:** 2026-05-18
**Owner:** mragank@mem0.ai
**Scope:** v1 of the holistic-import feature for `mem0-plugin/`

---

## 1. Problem

When a user installs `mem0-plugin`, mem0 starts empty. Everything Claude has already learned about their projects — every `CLAUDE.md` rule, every `MEMORY.md` auto-memory entry, every subagent's accumulated feedback — sits on local disk, invisible to mem0. The existing hooks only capture *new* state (`session_state`, `compact_summary`, agent `add_memory` calls). They cannot backfill what existed before install.

Competitive plugins either ignore this (claude-mem, Serena live-capture only) or auto-sync `CLAUDE.md` continuously without bulk import (Memory Store Plugin). No one performs a deliberate holistic backfill of Claude's prior state into a cloud memory layer.

This spec defines that backfill.

## 2. Goals

- Backfill into mem0 every piece of on-disk Claude state worth searching against later: `CLAUDE.md` hierarchy (+ `@imports`), `.claude/rules/`, `~/.claude/projects/*/memory/` (auto-memory + topic files), `~/.claude/agent-memory/*/` (subagent memory + topic files).
- Stay idempotent: re-running adds only new content, never duplicates existing chunks.
- Add the smallest possible new surface to the plugin (one new Python script + one new block in an existing hook + one marker file).
- Match existing plugin conventions: `_identity.py` for user resolution, urllib REST calls, stderr-only logging, `~/.mem0/` for state, `MEM0_API_KEY` for auth.

## 3. Non-goals (v1)

- **Continuous sync.** No watcher, no daemon, no per-edit re-import. Re-running the script is the supported way to pick up changes.
- **Slash command** (`/mem0 import`). Deferred. The CLI script invoked via Bash is enough for v1 since the agent can run it directly.
- **Cross-machine sync.** Each machine runs its own import. mem0 platform handles cross-machine reads.
- **Transient state import.** `~/.claude/history.jsonl`, `~/.claude/sessions/`, `~/.claude/todos/`, plan files — out of scope. High noise-to-signal.
- **Staleness re-prompting.** v1 hook is silent after first successful import. v2 may add a freshness check.
- **Sensitive content scrubbing.** Out of scope for v1; rely on user judgment (CLAUDE.md often contains internal URLs, API keys — same risk profile as agent-authored `add_memory` calls already in scope today).

## 4. Architecture

### Three deliverables — all minimal

1. **One new Python script:** `mem0-plugin/scripts/import_claude_state.py`. Patterned exactly on existing `on_pre_compact.py`: same logging setup, same urllib REST calls, same `_identity.py` for user resolution, same `exit 0` discipline for hook-invoked paths.
2. **One new conditional block** in existing `mem0-plugin/scripts/on_session_start.sh`. ~15 lines of bash after the existing identity + bootstrap output. Emits a one-time nudge to the agent if the marker file doesn't exist.
3. **One marker file:** `~/.mem0/imports/claude-state.json`. Same `~/.mem0/` directory already used for `hooks.log`.

### Invocation

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/import_claude_state.py [flags]

Flags:
  --dry-run           Print plan, don't upload.
  --reset             Delete marker and re-import everything.
  --no-infer          Upload chunks raw (infer=False), preserving wording.
  --source=<type>     Restrict to one source_type (claude_md|memory_md|rule|agent_memory|claude_local).
```

The agent runs the script via `Bash` when nudged by the hook. Power users run it directly from terminal. No new `mem0` CLI subcommand, no new Typer surface, no new package.

### Reused infrastructure (zero new)

| Need | Reused from |
|---|---|
| User identity | `_identity.py` / `_identity.sh` |
| REST API to mem0 | urllib pattern from `on_pre_compact.py` |
| Hook plumbing | existing `SessionStart` registration in `hooks.json` |
| Auth | `MEM0_API_KEY` env (already required) |
| Storage dir | `~/.mem0/` (already used for `hooks.log`) |
| Logging style | stderr logger, optional `~/.mem0/hooks.log` when `MEM0_DEBUG=1` |

## 5. Components

All inside `import_claude_state.py`. Flat, top-down, no classes. ~300 lines target.

### Discovery

`discover() -> list[Source]` globs the known paths:

| Path pattern | `source_type` | Notes |
|---|---|---|
| `/Library/Application Support/ClaudeCode/CLAUDE.md` (macOS) and platform equivalents | `claude_md_managed` | Org-level; rarely present, but supported. |
| `~/.claude/CLAUDE.md` | `claude_md_user` | User-global instructions. |
| `<cwd>/CLAUDE.md`, `<cwd>/.claude/CLAUDE.md`, ancestor `CLAUDE.md` walking up | `claude_md_project` | Project-level. Includes nested CLAUDE.md when discovered via @imports. |
| `<cwd>/CLAUDE.local.md` | `claude_local` | Personal project-specific. |
| `<cwd>/.claude/rules/**/*.md`, `~/.claude/rules/*.md` | `rule` | Path-scoped instruction files. |
| `~/.claude/projects/*/memory/MEMORY.md` | `memory_md` | Per-project auto-memory index. |
| `~/.claude/projects/*/memory/*.md` (non-MEMORY.md) | `memory_topic` | Topic files. |
| `~/.claude/agent-memory/*/MEMORY.md` | `agent_memory` | Subagent auto-memory index. |
| `~/.claude/agent-memory/*/*.md` (non-MEMORY.md) | `agent_memory_topic` | Subagent topic files. |

`Source(path, source_type, project_name?, subagent_name?)` — `project_name` extracted from the encoded path under `~/.claude/projects/`, `subagent_name` from `~/.claude/agent-memory/`.

### `@import` resolution

`resolve_imports(claude_md_path) -> list[Path]`. Follows Claude Code's loader semantics:
- `@path` syntax inside CLAUDE.md content
- Relative paths resolve relative to the file containing the import
- Absolute paths allowed
- `~/` expanded
- Max depth 5
- Cycle detection via a visited set
- Non-`.md` extensions allowed (Claude Code follows them too)

Discovered imports are merged into the discovery list with `source_type=claude_md_import`.

### Chunking

`chunk_markdown(text) -> list[Chunk]`:

- Split at `## ` (H2) by default.
- If a chunk exceeds **2000 chars**, descend to `### ` (H3) for that section.
- If a chunk is under **200 chars**, merge with the next sibling under the same parent heading.
- Code-fenced blocks (```` ``` ````) are never split mid-fence.
- If no headings at all, the file is one chunk.
- Token target: **~50–500 tokens per chunk** (the char heuristics — 200 char min, 2000 char max — map to roughly 50–500 tokens at the standard ~4 chars/token ratio for English prose).

Each `Chunk` carries:
```python
@dataclass
class Chunk:
    heading: str         # e.g. "## Coding Standards"
    body: str            # full section body, including the heading line
    content_hash: str    # sha256(body)
```

### Tagging

`tag_chunk(source, chunk) -> dict` returns the metadata dict attached to the `add_memory` call:

```python
{
    "source_file": "/Users/.../CLAUDE.md",
    "source_type": "claude_md_project",
    "section_heading": "Coding Standards",
    "project": "mem0-platform",     # null if not project-scoped
    "subagent": null,                # set for agent_memory sources
    "content_hash": "ab12...",
    "type": "convention",            # see heuristic below
}
```

`type` heuristic (matches the vocabulary in `mem0-plugin/skills/mem0-mcp/SKILL.md`):

| `source_type` | Default `type` | Heading-keyword overrides |
|---|---|---|
| `claude_md_*` | `convention` | Headings matching `prefer|preference|style` → `user_preference` |
| `claude_local` | `user_preference` | — |
| `rule` | `convention` | — |
| `memory_md` / `memory_topic` | `task_learning` | `bug|fix|debug` → `anti_pattern`; `decision|chose|picked` → `decision`; `never|always|critical` → `anti_pattern` |
| `agent_memory*` | `task_learning` | Same heading overrides as `memory_md` |

### Dispatch

`upload(chunks, user_id, infer=True) -> list[UploadResult]`:

- For each chunk in order:
  - If `content_hash` is already in the marker, skip.
  - POST `https://api.mem0.ai/v1/memories/` with:
    ```json
    {
      "messages": [{"role": "user", "content": "<chunk.body>"}],
      "user_id": "<resolved-user-id>",
      "metadata": { /* tag_chunk output */ },
      "infer": true
    }
    ```
  - Collect `memory_ids` from the response.
  - Write the chunk's entry to the marker file immediately (resume-on-crash safety).
- Sequential. No batching. No parallelism. Matches `on_pre_compact.py`.

### Marker I/O

`read_marker() -> Marker` / `write_marker(Marker)`. JSON at `~/.mem0/imports/claude-state.json`:

```json
{
  "schema_version": 1,
  "user_id": "mragankshekhar",
  "last_run_at": "2026-05-18T17:55:00Z",
  "imports": [
    {
      "file": "/Users/.../CLAUDE.md",
      "source_type": "claude_md_user",
      "imported_at": "2026-05-18T17:55:00Z",
      "chunks": [
        {
          "heading": "Coding Standards",
          "content_hash": "ab12...",
          "memory_ids": ["m_xyz"]
        }
      ]
    }
  ]
}
```

Per-chunk writes are atomic via write-temp-then-rename.

### Hook extension

Added to `mem0-plugin/scripts/on_session_start.sh` after the existing identity + bootstrap blocks:

```bash
# Holistic import nudge — only emit if marker doesn't exist yet
MARKER="$HOME/.mem0/imports/claude-state.json"
if [ ! -f "$MARKER" ]; then
  cat <<'EOF'

## Holistic import available

On-disk Claude state (CLAUDE.md, auto-memory, agent memory) has never been
imported into mem0. Run:

  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/import_claude_state.py --dry-run

to preview, then drop `--dry-run` to import. The import runs once; this nudge
goes away after the first successful run.
EOF
fi
```

`${CLAUDE_PLUGIN_ROOT}` is the variable already used by the existing hook scripts to reference the plugin's install path.

## 6. Data flow

### Happy path (first-time user)

```
1. User installs plugin → restarts Claude Code
2. SessionStart fires
   └─ on_session_start.sh:
      ├─ Identity block (existing)        → "Active user_id: ..."
      ├─ Bootstrap rubric (existing)      → "Call search_memories first..."
      └─ NEW: marker absent               → emit holistic-import nudge

3. Agent reads nudge, mentions it to user
4. User: "preview" → agent runs `python3 ... --dry-run`
5. Script: discover → chunk → print plan, return 0 (no upload)
6. Agent shows count, asks for confirmation
7. User: "go" → agent runs script without --dry-run
8. Script:
   for each chunk:
     - skip if content_hash already in marker (empty on first run)
     - POST /v1/memories/ with metadata + infer=True
     - append entry to marker file (atomic temp-and-rename)
   print "Imported X chunks from Y files, skipped Z duplicates"
9. Next SessionStart: marker exists → hook stays silent.
```

### Re-run scenarios

- **User edits a CLAUDE.md, re-runs script** → discover finds the same files; some chunks have unchanged content_hash (skipped via marker), some are new (uploaded). Marker is updated additively.
- **`--reset`** → marker file is wiped first, then full re-import runs. mem0's `infer=True` server-side dedup catches genuine duplicates.
- **`--no-infer`** → chunks uploaded with `infer=False`. Marker tracks content_hash, so re-runs remain idempotent client-side. Useful for content where wording must be preserved verbatim.
- **`--source=<type>`** → restrict discovery + upload to a single `source_type`.

### Concurrency

Sequential POSTs. Matches `on_pre_compact.py`. ~87 chunks (typical user with 15 projects + 2 subagents) completes in under a minute. No batching, no parallelism, no queueing.

## 7. Error handling

The hook block must never break SessionStart. The CLI script can exit non-zero on real failures so users / agents notice.

| Failure | Behavior |
|---|---|
| `MEM0_API_KEY` missing | CLI: print *"Set MEM0_API_KEY first — see plugin README"*, exit 1. Hook: existing `[ -z "$MEM0_API_KEY" ] && exit 0` guard short-circuits before the nudge. |
| Network error / timeout | Log to stderr, skip chunk, continue. Final summary lists failures + *"re-run to retry"*. |
| 401 / auth error | Stop immediately. Print *"Auth failed — check MEM0_API_KEY"*. Don't keep hammering. |
| 429 rate limit | Backoff once (sleep 2 s), retry once, then skip-and-continue. |
| 5xx | Log + skip chunk + continue. |
| File read error or file disappeared between scan and read | Log warning, skip, continue. |
| Malformed markdown | Treat whole file as one chunk. Truly unreadable files are skipped + logged. |
| `@import` cycle or depth > 5 | Detected, logged, first occurrence honored, rest skipped — matches Claude Code's loader. |
| Marker file JSON corruption | Treat as absent, log warning, continue. Next run rewrites cleanly. |
| Script killed mid-run | Marker writes per chunk (not per file, not at end) → re-run resumes from the next un-marked chunk. |
| Hook block tooling missing (`jq`, etc.) | `2>/dev/null || true` wraps the block — never breaks SessionStart. |

## 8. Testing

Three layers, all using existing tooling (pytest + `unittest.mock`).

### Unit tests — `tests/plugin_scripts/test_import_claude_state.py` (new file, new dir under existing `tests/`)

| Function under test | Cases | Approximate count |
|---|---|---|
| `chunk_markdown` | no headings, only H1, deeply nested headings, oversized H2 → descends to H3, undersized siblings merged, code fences not split mid-fence | ~10 |
| `tag_chunk` | every `source_type` → expected default `type`; heading-keyword overrides | ~8 |
| `resolve_imports` | relative path, absolute path, `~/` expansion, cycle, depth limit, missing target | ~6 |
| `read_marker` / `write_marker` | roundtrip, corrupted JSON, missing file, schema_version migration | ~4 |

### Integration tests — same file

- End-to-end with `urllib.request.urlopen` mocked. Fixture directory with one fake CLAUDE.md (with one `@import`) + one fake `MEMORY.md` + one fake agent-memory file. Asserts: discover finds 4 files, chunker produces N chunks, dispatcher POSTs N times with correct metadata payloads, marker file written with the expected structure.
- One test for `--reset` flow (marker wiped, full re-upload).
- One test for `--no-infer` flow (`infer: false` in payload, content_hash still tracked).
- One test for partial-failure resume (kill mid-run, re-run, asserts only missing chunks are uploaded).

### Manual smoke

- Documented in the PR description: run against a real mem0 account with `MEM0_USER_ID=mem0_import_smoke_$DATE`. Confirm chunks appear, are searchable, and `metadata.source_type` filters work as advertised in `mem0-plugin/skills/mem0-mcp/SKILL.md`.

### CI

No new workflow. The existing `ci.yml` runs `pytest tests/` — the new test file is picked up automatically. No new dependencies.

## 9. File layout

```
mem0-plugin/
  scripts/
    on_session_start.sh           # extended (one new conditional block)
    import_claude_state.py        # NEW (~300 lines)
    _identity.py                  # unchanged, reused
    _identity.sh                  # unchanged, reused
    on_pre_compact.py             # unchanged (pattern reference)
tests/
  plugin_scripts/                 # NEW directory
    __init__.py                   # NEW (empty)
    test_import_claude_state.py   # NEW
~/.mem0/
  imports/
    claude-state.json             # marker, written by the script at runtime
```

## 10. Open questions

None blocking. Everything below is a deliberate v2 deferral:

- **Continuous sync** — should a future hook watch for changes to `MEMORY.md` and incrementally import? Out of scope for v1.
- **Slash command `/mem0 import`** — convenience wrapper inside Claude Code. Easy to add later; not needed now since agent can run the script directly.
- **Staleness re-prompting** — should the SessionStart hook re-nudge if marker is >N days old or if `find` shows files newer than `last_run_at`? Deferred.
- **Codex / Cursor parity** — `codex-hooks.json` and `cursor-hooks.json` already reference the same `on_session_start.sh` we're modifying, so the nudge propagates to those clients for free. The Python script itself is client-agnostic (uses `${CLAUDE_PLUGIN_ROOT}` env interpolation, falls back to script location). Confirm via a smoke run on each client during implementation.
- **Sensitive-content scrubbing** — secrets detection in CLAUDE.md before upload. Out of scope; consistent with current plugin treatment of agent-authored memories.
