# Changelog

All notable changes to the Mem0 plugin will be documented in this file.

## 0.2.0

### Added

- **Project-scoped memories:** Deterministic `project_id` from git remote (`_project.sh` / `_project.py`). Memories are now isolated per-repo via `metadata.project_id` on every `add_memory` and `search_memories` call. Same repo cloned twice → same `project_id`.
- **Branch-aware tagging:** `metadata.branch` stamped on session-state and compact-summary memories. Enables branch-scoped recall (e.g. "what was I doing on feature/auth-rewrite?").
- **Auto-import of project files:** SessionStart detects CLAUDE.md, AGENTS.md, .cursorrules, .windsurfrules, mem0.md — hashes them (SHA-256), imports changed files as `project_profile` memories. Idempotent across sessions.
- **Active identity banner:** SessionStart now prints `user=X | project=Y | branch=Z | memories=N` instead of a silent bootstrap.
- **Session-end report:** Stop hook prints `Session: wrote N memories, retrieved M. Categories touched: ...` and appends to `~/.mem0/session-log.md`.
- **`/mem0:onboard` skill:** Post-install wizard — verifies API key, detects and imports project files, installs coding categories, prints setup summary. 30 seconds to value.
- **`/mem0:tour` skill:** Shows all memories for the current project grouped by category. Proof-of-value demo.
- **`/mem0:switch-project` skill:** Manual `project_id` override for monorepos and non-git directories. Persists to `~/.mem0/project_map.json`.
- **Session stats tracker** (`session_stats.py`): Tracks memory adds/searches per session for the end-of-session report.

### Changed

- All hooks and `mem0-mcp/SKILL.md` now include `project_id` in every filter and metadata example.
- SessionStart banner replaces the previous "## Mem0 Identity" block with a compact one-liner.
- `on_pre_compact.py` and `capture_compact_summary.py` now include `project_id` and `branch` in stored metadata.

## 0.1.3

### Fixed

- **user_id resolution no longer derives from `MEM0_API_KEY`.** v0.1.2 changed the resolver to fall back to `"mem0-" + sha256(MEM0_API_KEY)[:12]` ahead of `$USER`, which silently moved every existing user to a new bucket on update. Memories written under the previous `$USER` value became unreachable from the plugin. Resolution is now back to `MEM0_USER_ID` → `$USER` → `"default"`.
- Dropped the "regardless of which machine you're on" line from the SessionStart bootstrap, since cross-machine consolidation now requires setting `MEM0_USER_ID` explicitly.

### Notes for users upgrading from 0.1.2

- The `~/.mem0/identity.json` cache file is no longer read or written. Safe to delete.
- If you wrote memories during the v0.1.2 window, they live under `mem0-<sha256(api_key)[:12]>`. To recover: temporarily `export MEM0_USER_ID=mem0-<hash>`, search/export, then unset.
- Want a single bucket across machines (the original goal of #5076)? Set `MEM0_USER_ID` explicitly in your shell profile. The plugin will not auto-derive one.

## 0.1.2

### Added

- Deterministic `user_id` resolver (`_identity.sh` / `_identity.py`) — **reverted in 0.1.3, see above.**
- SessionStart-compact handler (`capture_compact_summary.py`) that stores the post-compaction summary as a memory with `metadata.type=compact_summary`.
- Coding-taxonomy setup script (`setup_coding_categories.py`) — one-shot `project.update(custom_categories=[...])` for `architecture_decisions`, `anti_patterns`, `task_learnings`, `tooling_setup`, `bug_fixes`, `coding_conventions`, `user_preferences`.
- Opt-in hook logging via `MEM0_DEBUG=1` → `~/.mem0/hooks.log`.
- `mem0-mcp` skill replacing the Claude-Code-specific `mem0-codex` skill.

### Fixed

- `session_id` now written to memory metadata (`on_pre_compact.py`).
- SessionStart bootstrap exits silently when `MEM0_API_KEY` is unset.
- `block_memory_write.sh` regex tightened to `MEMORY.md` / `.claude/memory/*` — no longer blocks `docs/memory/*.md`.
- Removed duplicate PreCompact write path (kept agent-driven, dropped the parallel Python REST entry from `hooks.json` / `cursor-hooks.json`).
- Hook-side captures (`session_state`, `compact_summary`) now set `expiration_date = today + 90 days`.

## 0.1.1

- Cursor plugin fully functional (`#4547`).
- Codex plugin support and integration docs (`#4665`).
- Codex lifecycle hooks via opt-in installer (`#4917`).
- Removed invalid keys from Claude plugin config (`#4821`).

## 0.1.0

- Initial release: Mem0 plugin for Claude Code and Cursor (`#4518`).
