# Changelog

All notable changes to the Mem0 plugin will be documented in this file.

## 0.2.4

### Fixed

- **PostToolUse matcher mismatch (`hooks.json:81`):** Changed from `mcp__mem0__` to `mcp__mem0__|mcp__plugin_mem0_mem0__`. Root cause of session stats recording nothing — 146 consecutive "no memory operations" entries. Unblocks `/mem0:stats` session line, stop-hook report, and `session_stats.py` tracking.
- **File-read hook noise (`on_file_read.sh`):** Replaced bare-filename semantic search with `metadata.files` filter + score threshold (≥ 0.4). Falls back to basename search if metadata filter returns nothing. Eliminates irrelevant context injection on every Read.
- **`/mem0:pin` uses v3-removed `immutable=True`:** Removed Step 3a entirely. Standardized on `metadata.pinned: true` (which `dream/SKILL.md` already respects during pruning). Fixed unconditional `...` appended to short pin confirmations.
- **`/mem0:list-projects` undercounts (implicit null scoping):** Dual-query approach — runs both null-scoped and app-scoped `get_memories` calls, merges by ID. Handles legacy `metadata.project_id` and `metadata.project` fields.
- **`/mem0:peek` free-text search on memory IDs:** Detects bare hex IDs (`^[a-f0-9]{8}$`) and `[mem0:<hex>]` citation refs, routes to `get_memory` direct lookup instead of semantic search.
- **Dead `PostToolUseFailure` hook block:** Removed entirely — this hook event does not exist in Claude Code.

### Added

- **Session ID capture (`on_session_start.sh`):** Extracts `session_id` from Claude Code stdin JSON, persists to `/tmp/mem0_session_id_$USER`. Falls back to timestamp-based ID. Enables `run_id`-based session scoping.
- **`run_id` injection (`enforce_metadata_defaults.sh`):** Reads session ID from temp file, injects as `run_id` into every `add_memory` call. Tags all memories with session identity for entity-scoped filtering.
- **`min_score`, `metadata_filters`, `rerank`, `threshold` params (`_search.py`):** `search_memories()` now accepts `min_score: float` to filter low-relevance results, `metadata_filters: dict` for field-level filtering, `rerank: bool` for managed reranker, and `threshold: float` (default 0.3, up from platform default 0.1) for server-side relevance gating. Existing callers unaffected (new params have defaults).
- **Rerank on tour/peek:** `/mem0:tour` and `/mem0:peek` search calls now pass `rerank=true` for better result ordering (+150–200ms latency, significantly improved precision).
- **`/mem0:stats` session query via `run_id`:** Queries memories by `run_id` filter for API-backed session counts. Cross-checks against local stats file. Shows truncated session ID in output.

### Removed

- **`/mem0:protocol` skill:** Routing table fully superseded by individual skill descriptions (auto-trigger). Operational guidelines (search patterns, metadata rules) covered by `enforce_metadata_defaults.sh` hook and individual skill bodies.

### Changed

- **All 17 skill descriptions:** Rewritten per Claude skill best practices — each now includes what the skill does AND when to trigger it, with specific keywords for auto-discovery. Average length 200–270 chars (under 1024 max). Third person, action verbs.
- **Onboarding auto-trigger (`on_session_start.sh`):** Replaced 3-state marker-file logic with memory-count detection. New project (0 memories) → prompts Claude to invoke `/mem0:onboard`. No marker files, no OAuth state. Simplified no-API-key path to single inactive banner.

## 0.2.3

### Added

- **Read hook (`on_file_read.sh`):** `PreToolUse(Read)` hook that searches mem0 for memories tagged with the file being opened and injects them as context. Skips non-code files, lockfiles, and `node_modules/`. Deduplicates repeated reads within a session.
- **Shared search module (`_search.py`):** Wraps `POST /v3/memories/search/` into a reusable `search_memories()` call with `format_results_for_context()` for consistent `[type] content [mem0:id]` display. Used by all pre-fetch hooks.
- **User settings (`load_settings.py`):** Loads config from `~/.mem0/settings.json` with 9 keys: `auto_save`, `auto_search`, `search_limit`, `retention_session_days`, `confidence_threshold`, `output_style`, `debug`, `skip_tools`, `capture_tools`. Supports `init` subcommand for first-run creation.
- **`/mem0:forget` skill:** Standalone skill for deleting memories by search query or UUID with confirmation. Supports undo-last-N via `session_stats.py peek`.
- **`/mem0:peek` skill:** Compact quick-search with one-liner output. Runs 2 parallel searches (broad + `decision`-filtered), deduplicates by ID.
- **`/mem0:memory-reviewer` skill:** Read-only memory quality audit. Scans for near-duplicates (>60% noun overlap), contradictions, low-confidence entries, untagged memories, and stale entries (>180 days). Refers to `/mem0:dream` for remediation.
- **`/mem0:context-loader` skill:** Pre-fetch agent that runs 2–4 parallel `search_memories` calls across query angles and type filters, deduplicates, outputs up to 10 memories. Silent on empty results.
- **Compact memory output style (`output-styles/compact-memory.md`):** `[<type>] <content, max 80 chars> [mem0:<short_id>]` format used by `peek`, `tour`, and inline search display.
- **`userConfig` in `.claude-plugin/plugin.json`:** `api_key` field (`sensitive: true`) enables key storage via `claude plugin configure mem0`.
- **OAuth support:** `authorizationUrl` added to `.mcp.json` for OAuth flow alongside token-based auth.
- **Tests:** `test_search.py`, `test_rubric_dedup.py`, `test_on_file_read.py`.

### Changed

- **Skills renamed:** All `mem0-*` prefixed skill directories renamed to shorter forms (e.g., `mem0-dream` → `dream`, `mem0-mcp` → `protocol`, `mem0-tour` → `tour`). 12 skills renamed total.
- **Pre-fetch on bash errors:** `on_bash_output.sh` now performs actual `search_memories` calls via `_search.py` instead of emitting search query templates as text.
- **Session-resume pre-fetch:** `on_user_prompt.sh` detects resume phrases ("where did we leave off", "continue from where") and pre-fetches `session_state` + `decision` memories.
- **Remember-intent routing:** `on_user_prompt.sh` detects save phrases ("remember this", "don't forget that") and routes to `/mem0:remember` skill instead of raw `add_memory`.
- **Rubric deduplication:** Search guidance rubric injected only on first user prompt per session via flag file.
- **Namespace-agnostic tool matching:** `on_post_tool_use.sh` and `on_tool_failure.sh` now use wildcard suffix matching (`*__add_memory`) instead of hardcoded `mcp__mem0__` prefix.
- **API key resolution:** `_identity.sh`/`_identity.py` now check `CLAUDE_PLUGIN_OPTION_API_KEY` (from `userConfig`) before legacy `CLAUDE_PLUGIN_OPTION_MEM0_API_KEY`.
- **Session start:** Three-state no-key handling (first run → auto-onboard, OAuth mode → proceed, neither → inactive banner). Banner now shows `auth=api_key|oauth`.
- **Hook timeouts:** `on_user_prompt.sh` and `on_bash_output.sh` raised from 5s to 12s.
- **Compact prompts:** `on_task_completed.sh` and `on_stop.sh` replaced multi-step checklists with single-line directives (0–2 durable facts max).
- **`/mem0:dream`:** Removed `--forget` (now standalone `forget` skill) and `--schedule` flags.
- **`/mem0:health`:** Removed `--fix` auto-fix mode; output condensed to `PASS/FAIL CheckName Detail` one-liners.
- **`/mem0:protocol` (was `mem0-mcp`):** Added 14-entry natural-language-to-skill routing table. _(Removed in 0.2.4 — superseded by skill descriptions.)_
- **CLI config fallback removed:** `_identity.sh`/`_identity.py` no longer read `~/.mem0/config.json`; API key resolution is env-var-only.
- **`auto_import.py`:** Added content-hash deduplication to skip files with identical content within a single import run.
- **All skill descriptions:** Shortened to concise one-liners.

### Fixed

- **Namespace-agnostic tool name parsing in `on_tool_failure.sh`:** `${TOOL_NAME##*__}` correctly strips any MCP namespace prefix, not just `mcp__mem0__`.
- **`_identity.py`/`_identity.sh`:** `CLAUDE_PLUGIN_OPTION_API_KEY` env var was not checked, causing key-not-found when using `userConfig`.
- **Three previously failing tests** (`test_on_file_read.py`, `test_rubric_dedup.py`, `test_write_path.py`) fixed after hook changes.

### Removed

- **`/mem0:dream --forget` flag:** Extracted to standalone `forget` skill.
- **`/mem0:dream --schedule` flag:** Use Claude Code's built-in `/schedule` command instead.
- **`/mem0:health --fix` flag:** Auto-fix mode removed entirely; use `/mem0:dream` for remediation.
- **CLI dependency for key management:** All `~/.mem0/config.json` fallback code removed.

## 0.2.2

### Fixed

- **Duplicate memory writes on compaction:** `on_pre_compact.py` was running as both primary and backup capture path. Now reads `session_stats` and skips if agent already stored 2+ memories. `on_stop.sh` and `on_session_end.sh` were both calling `on_pre_compact.py`, creating double captures — removed redundant calls.
- **Verbose session-state blobs:** `on_pre_compact.py` `build_content()` was producing 5000+ char structured markdown. Now produces minimal 2-line summary (`Working on:`, `Files touched:`), relying on `infer=True` for extraction.
- **Pre-compaction prompt rewrite:** Instruction changed from "store a single large `session_state` blob with `infer=False`" to "store 0–3 durable facts per session (15–50 words each), one per `add_memory` call, tagged by category."
- **False-positive error detection:** `on_bash_output.sh` and `on_user_prompt.sh` error grep pattern was too broad, triggering on routine test/linter output. Now uses two-tier approach: high-signal patterns (`Traceback`, `panic:`, `FATAL:`) fire always; lower-signal (`Error:`, `Exception:`) require 2+ occurrences.
- **Background `on_pre_commit.py` on every git commit:** `on_git_commit_capture.sh` was storing `commit_context` memories regardless of usefulness. Background call removed; hook now only performs memory search. `on_pre_commit.py` deleted.
- **Post-commit prompt always firing:** `on_post_commit.sh` now gated behind `settings.commit_prompts: true` in `mem0.md` (defaults to off).
- **Project ID lost after folder rename:** `_project.py` only looked up `project_map.json` by CWD path. Added remote-hash fallback: hashes `git remote.origin.url` to a 16-char key, self-heals map on hit.
- **Subagent skip list hardcoded:** `on_subagent_stop.sh` now reads `settings.subagent_skip` from `mem0.md` instead of hardcoded `Explore|Plan`.
- **Auto-import missed project-root files:** `auto_import.py` only searched CWD. Added `_git_root()` helper to also search git root when invoked from subdirectory.
- **Concurrent `ensure_deps.sh` install race:** Multiple parallel sessions could corrupt the venv. Added lock directory with 60s spin-wait and `.install-failed` sentinel.
- **Telemetry `distinct_id` used MD5:** Changed to SHA-256 (truncated 32 chars).
- **Telemetry caller props could override system props:** Moved system fields after spread so they always win.
- **Plugin version hardcoded in `telemetry.py`:** Replaced with `_load_plugin_version()` reading from `plugin.json`.
- **Onboard marker race:** Marker now created in `on_session_start.sh` when prompt is first displayed, not after skill completes.

### Changed

- **`capture_compact_summary.py`:** `infer` changed from `False` to `True` so platform can extract structured facts.
- **Chunking utilities extracted to `_chunking.py`:** `split_by_headers`, `split_by_hr_or_headers`, `filter_and_truncate` moved from `import_competing_tools.py` to shared module.
- **`auto_import.py` now chunks Markdown files:** `.md` files split by `## ` headers before import instead of single blob.
- **`enforce_metadata_defaults.sh`:** New `PreToolUse` hook on `add_memory` for all three editors. Injects default metadata (`confidence: 0.7`, `source: "auto_capture"`, `type: "task_learning"`) when agent omits them.
- **`mem0.md` Settings section parsing:** `parse_mem0_config.py` now parses `Settings` section; added `--key <dotted.path>` CLI argument for programmatic lookup.
- **Project config display condensed:** Session start shows compact summary line instead of raw JSON dump.

### Added

- `scripts/_chunking.py` — shared content-chunking utilities.
- `scripts/enforce_metadata_defaults.sh` — metadata defaults injection hook.
- `parse_mem0_config.py --key` — CLI accessor for individual `mem0.md` config keys.
- **Native `MEMORY.md` detection:** `on_session_start.sh` detects Claude Code auto-memory and prompts to disable or run `/mem0:import`.
- **`/mem0:list-projects` skill:** Discovers all project `app_id` scopes by paginating `get_memories` without an `app_id` filter.
- **`/mem0:tour` cross-project mode** (`--all-projects`) and peek mode (query argument).
- **`/mem0:stats` weekly digest mode** (`--weekly`).
- **`/mem0:dream --forget` mode:** Search-confirm-delete flow with undo-last-write.
- **`/mem0:import --tools` flag:** Import from competing AI tool configs.
- `conftest.py` — `_clean_project_map` autouse fixture preventing cross-test pollution.

### Removed

- `scripts/on_pre_commit.py` — source of unwanted background writes on every commit.
- **`/mem0:digest` skill** — merged into `/mem0:stats --weekly`.
- **`/mem0:forget` skill** — merged into `/mem0:dream --forget`.
- **`/mem0:import-tools` skill** — merged into `/mem0:import --tools`.
- **`/mem0:peek` skill** — merged into `/mem0:tour <query>`.
- `tests/test_pre_commit.py` — tests for deleted script.

## 0.2.1

### Added

- **11 new skills:** `/mem0:dream` (memory consolidation), `/mem0:export` (portable YAML-frontmatter export), `/mem0:import` (re-import exported memories), `/mem0:import-tools` (import from Cursor/Copilot/Cline/Continue configs), `/mem0:forget` (delete with confirmation), `/mem0:health` (diagnostic check — API key, MCP connectivity, read/write), `/mem0:peek` (compact quick-search), `/mem0:pin` (mark memory as high-priority), `/mem0:remember` (quick verbatim store with auto-classification), `/mem0:stats` (session + lifetime statistics), `/mem0:digest` (weekly memory summary).
- **8 new hook scripts:** `on_bash_output.sh` (scan bash output for errors, surface `anti_pattern`/`bug_fix` memories), `on_git_commit_capture.sh` (detect git commit/merge/rebase, search relevant memories), `on_post_commit.sh` (prompt to save commit learnings), `on_post_compact.sh` (recovery prompt to reload context after compaction), `on_session_end.sh` (last-chance transcript capture with dedup marker), `on_subagent_stop.sh` (remind to capture learnings from non-Explore/Plan subagents), `on_tool_failure.sh` (classify MCP failures as auth/rate-limit/network, suggest recovery), `on_pre_commit.py` (capture staged changes via REST API).
- **PostHog telemetry (`telemetry.py`):** Anonymous, fire-and-forget, 10% sampled. Uses stdlib `urllib` (no SDK dependency). Sends event type, platform, plugin version, anonymized identity. Never sends memory content or API keys. Opt-out via `MEM0_TELEMETRY=false`.
- **10 new memory categories in `setup_coding_categories.py`:** `dependency_decisions`, `performance_findings`, `security_constraints`, `testing_patterns`, `data_model`, `api_contracts`, `deployment_runbook`, `team_norms`, `domain_glossary`, `experiment_results`.
- **Dependency management (`ensure_deps.sh`):** Installs `mem0ai` into persistent venv at `${CLAUDE_PLUGIN_DATA}/venv`. Skips re-install if `requirements.txt` hash unchanged. Runs on `Setup(init|maintenance)` hook and every `SessionStart`.
- **Competing tool importer (`import_competing_tools.py`):** Parses and uploads configs from `.cursorrules`, `.github/copilot-instructions.md`, `memory-bank/`, `.continue/rules.md`. Splits by Markdown headers/horizontal rules.
- **Export file parser (`parse_export_file.py`):** Parses YAML-frontmatter Markdown format into JSON array.
- **Config parser (`parse_mem0_config.py`):** Reads `mem0.md` and extracts `Retention` section into category-to-days mapping.
- **Auto-onboarding:** `on_session_start.sh` detects first-time projects and triggers `/mem0:onboard` automatically.
- **`mem0.md` config loading:** Session start parses `mem0.md` and injects project config into context.
- **Inactive API key banner:** Shows `Mem0 Inactive` with `api_key=NOT_SET` instead of silently exiting.
- **`requirements.txt`:** Declares `mem0ai` as plugin's Python dependency.
- **Tests:** `test_coding_categories.py`, `test_import_competing_tools.py`, `test_parse_export_file.py`, `test_parse_mem0_config.py`, `test_pre_commit.py`, `test_session_stats.py`, `test_telemetry.py`, `test_write_path.py`.

### Changed

- **API scoping: `metadata.project_id` → `app_id`:** All scripts and skills now pass `project_id` as top-level `app_id` parameter instead of inside `metadata`. Affects `auto_import.py`, `capture_compact_summary.py`, `on_pre_compact.py`, all stop hooks, all skill instructions.
- **API endpoint: v1 → v3:** `auto_import.py`, `capture_compact_summary.py`, `on_pre_compact.py` now call `/v3/memories/add/`.
- **API key resolution:** `_identity.py` and `_identity.sh` now check `CLAUDE_PLUGIN_OPTION_MEM0_API_KEY` (Claude Code `userConfig` env var) as fallback after `MEM0_API_KEY`.
- **`session_stats.py`:** Added per-category counters, rolling list of up to 50 recent memory IDs, `peek` subcommand for non-destructive stat reading.
- **`setup_coding_categories.py`:** Now imports `mem0ai` from managed venv via `sys.path` injection.
- **`on_stop_cursor.sh`:** Added `loop_count` guard to prevent re-entry loops.
- **`on_stop.sh`:** Removed `set -e` so session-end reminder always emits even if `session_stats.py` fails. Added dedup marker (`~/.mem0/.captured_<session_id>`).
- **`on_user_prompt.sh`:** Detects source file paths in prompt and adds `metadata.files contains` search filter. Handles no-API-key case gracefully.
- **`/mem0:tour`:** Replaced 7 parallel type-filtered `search_memories` calls with single `get_memories(app_id=...)` + 3 broad searches (type filtering misses auto-categorized memories).
- **`/mem0:onboard`:** Added SDK install step, changed MCP check to use ToolSearch, writes onboard marker to prevent re-triggering.
- **`/mem0:mcp`:** Added 16-row category-to-query routing table, inline citations requirement, `branch` in metadata requirement.

### Fixed

- **`auto_import.py`, `capture_compact_summary.py`, `on_pre_compact.py`:** Were reading `MEM0_API_KEY` directly; now use `resolve_api_key()` so `CLAUDE_PLUGIN_OPTION_MEM0_API_KEY` is honored.
- **`on_pre_compact.py`:** `resolve_project_id()` and `resolve_branch()` now receive `cwd` from hook input instead of `os.getcwd()`, fixing incorrect identification when hook fires in different directory.
- **`on_stop_codex.sh`, `on_stop_cursor.sh`:** Missing `_identity.sh` source call; API key resolution via `userConfig` fallback was broken.
- **`on_post_tool_use.sh`:** Input field corrected from `tool_result` to `tool_output` to match hook JSON schema.

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
