# Changelog

All notable changes to the Mem0 plugin will be documented in this file.

## 0.2.9 — File-context injection, session summaries & activity timeline

### Added

- **File-context injection (`PreToolUse/Read` hook):** Before Claude reads a file, the new `on_file_read.sh` hook searches mem0 for memories that reference that file path and injects a compact timeline of prior work as `additionalContext`. Gives Claude "I've seen this file before and here's what I remember" context automatically. Gates on file size (>= 1,500 bytes), 5-second hard timeout, silent skip on any failure. Applies to Claude Code, Codex, and Cursor (`on_file_read_cursor.sh`).
- **Stop hook session summary (`on_stop.sh`):** On session end, parses the transcript JSONL, extracts the last assistant message and files touched, builds a structured prompt, and stores it via the mem0 API with `infer=True` — letting the platform's backend AI extract structured facts (request, decisions, learnings, next steps). Memories are stored as `metadata.type=session_summary` with 90-day expiry. Guards: skips subagent sessions (`agent_id` present), dedup via marker file, always exits 0. Applies to Claude Code, Codex, and Cursor (`on_stop_cursor.sh`).
- **SessionStart activity timeline (`session_timeline.py`):** On startup (when project has existing memories), fetches the 10 most recent memories and renders a compact timeline with type icons, age indicators, and short text below the existing banner. Shows recent decisions, bug fixes, and session summaries at a glance. 5-second timeout — if the API is slow, the timeline silently skips while the banner still displays.
- **`scripts/file_context.py`:** Core Python module for file-context injection. Searches mem0 cloud API with both relative and absolute file paths, deduplicates results, formats as compact timeline with type icons and memory age.
- **`scripts/capture_session_summary.py`:** Core Python module for Stop hook. Reads transcript JSONL (tail 3,000 lines), extracts last assistant message, extracts file paths from tool_input fields, strips system tags and `<private>` blocks, stores via mem0 API.
- **`scripts/session_timeline.py`:** Core Python module for SessionStart timeline. Fetches recent memories from mem0 API, formats with type icons, relative age, and short text.

### Changed

- **`on_session_start.sh`:** On startup (when memories > 0), calls `session_timeline.py` to inject a compact recent activity timeline below the existing banner and rubric instructions.
- **`hooks/hooks.json`:** Added `PreToolUse` matcher for `Read` (5s timeout) and `Stop` hook (30s timeout).
- **`hooks/codex-hooks.json`:** Added `PreToolUse` matcher for `Read` (5s timeout) and `Stop` hook (30s timeout).
- **`hooks/cursor-hooks.json`:** Added `preToolUse` matcher for `Read` (5s timeout) and `stop` hook (30s timeout).

## 0.2.8 — Automatic coding categories & global search

### Added

- **Global search mode (`global_search` setting):** New `global_search` toggle in `~/.mem0/settings.json` (default: `false`). When enabled, `search_memories` and `get_memories` calls use `{"OR": [{"user_id": "*"}]}` instead of the per-user per-project `AND` filter — returning all memories across all users and all `app_id` scopes in the platform project. Writes (`add_memory`) still tag with the current `user_id` and `app_id`. Solves the team-shared-memory use case where multiple team members need access to all memories regardless of which repo or user created them. Works on Claude Code, Cursor, and Codex.
- **`/mem0:switch-project --global` / `--no-global`:** Enables or disables global search via the switch-project skill. Persists to `~/.mem0/settings.json`. No manual config editing needed.
- **Session banner scope indicator:** Banner shows `scope=global` when global search is active instead of `project=<app_id>`.
- **Global-aware memory count:** Session start memory count query uses the global filter when `global_search` is enabled.
- **Background coding-category setup (`scripts/auto_setup_categories.py`):** The coding-focused category taxonomy (17 categories tuned for development work) is now installed automatically in the background on session start — the same way `auto_import.py` imports `CLAUDE.md`/`AGENTS.md`. Users are no longer asked to configure it during onboarding. Mirrors the auto-import design: resolves the API key, holds a lock file (`~/.mem0/categories_setup.lock`), reuses the proven `setup_coding_categories.py` taxonomy + `project.update` path via the plugin venv, logs to stderr only, and always exits 0 so it can never block a session.
- **Per-account state gating (`~/.mem0/categories_setup.json`):** Keyed by a hash of the API key → a hash of the taxonomy. Categories are scoped to the mem0 project tied to the API key (not the local repo), so setup runs once per account and skips all network calls thereafter — re-applying only if the taxonomy itself changes.
- **`tests/test_auto_setup_categories.py`:** Covers fingerprint determinism/sensitivity, state-file load/save/gating, and idempotent apply via an injected fake client (no SDK, no network).

### Changed

- **`on_session_start.sh`:** Spawns `auto_setup_categories.py` in the background on `startup` (alongside `auto_import.py`), preferring the venv python so the SDK is available. Covers Claude Code, Cursor, and Codex, which all route SessionStart through this script.
- **`/mem0:onboard` Step 5 is no longer interactive:** Removed the `Install coding categories? [Y/n]` prompt. Categories now configure automatically in the background; the onboarding step only verifies status and applies them if the background run hasn't finished yet — mirroring how Step 4 (project-file import) already works.
- **Session-start "new project" hint** now notes that coding categories install automatically in the background.

## 0.1.0 — Antigravity

### Added

- **Antigravity plugin** (`.antigravity/`): Restructured to follow the same shared-infrastructure pattern as Claude Code, Cursor, and Codex. Self-contained plugin directory with `plugin.json`, `mcp_config.json`, `hooks/hooks.json` (own file), `scripts/` (symlink → `../scripts/`), and `skills/` (symlink → `../skills/`). Installable via `agy plugin install .antigravity` or `npx degit mem0ai/mem0/mem0-plugin/.antigravity ~/.gemini/config/plugins/mem0`. Uses `contextFileName: "AGENTS.md"` per Antigravity convention.
- **Codex hooks parity:** Added missing `PreToolUse` Write/Edit/MultiEdit block and `PreCompact` hook to Codex hooks config, bringing it to full parity with Claude Code.

### Changed

- **Antigravity plugin directory:** Renamed `.antigravity-plugin/` → `.antigravity/` to match the naming convention of `.claude-plugin/`, `.cursor-plugin/`, `.codex-plugin/`. Plugin is now self-contained so `agy plugin install` and `npx degit` both work.
- **Antigravity hooks:** Hooks now live directly in `.antigravity/hooks/hooks.json` as a standalone file — no indirection.
- **Antigravity install command:** Updated from `npx degit mem0ai/mem0/mem0-plugin` to `npx degit mem0ai/mem0/mem0-plugin/.antigravity`. Added `agy plugin install` as alternative for local clones.

### Removed

- **Stale root-level files:** Deleted `mem0-plugin/hooks.json`, `mem0-plugin/mcp_config.json`, `mem0-plugin/plugin.json` — leftover artifacts from before plugin restructuring into per-editor subdirectories. Nothing referenced them; install commands point to `.antigravity/`.

## 0.2.7

### Fixed

- **First-install auth failure (closes #4876):** Removed `authorizationUrl` from `.mcp.json`. When both a static `Authorization` header and `authorizationUrl` were present, Claude Code preferred the OAuth flow, which failed on reconnect — leaving new users stuck with only `authenticate`/`complete_authentication` stub tools. Authentication now uses the `MEM0_API_KEY` header exclusively; no browser OAuth flow is triggered.
- **Onboarding skill removed OAuth step:** `/mem0:onboard` Step 2 no longer guides users through a browser-based OAuth login. The MCP server authenticates via the API key set in Step 1.
- **Removed `claude plugin configure mem0` references:** This CLI command does not exist. The `userConfig` mechanism works through the plugin enable UI prompt — Claude Code prompts for the API key when the plugin is first enabled and stores it securely in the system keychain. Updated session start banner, onboarding skill, identity script comments, and manual testing guide.

## 0.2.6

### Fixed

- **Memory count zero / stats and tour showing 0 memories:** The `run_id: "*"` wildcard filter — added in the initial v0.2.6 fix — returns 0 on both the v3 list endpoint (`/v3/memories/`) and search endpoint (`/v3/memories/search/`) when memories were written without a `run_id` (which is all memories since v0.2.6 stopped setting `run_id` on `add_memory`). Removed `run_id: "*"` from: `on_session_start.sh` count queries, `enforce_metadata_defaults.sh` hook injection (was injecting into every `search_memories` and `get_memories` call), `_search.py` search payload, `/mem0:stats` and `/mem0:tour` skill instructions. All read paths now use simple `user_id` + `app_id` filters without `run_id`, matching how v0.2.3 worked.
- **`add_memory` no longer sets `run_id`:** Session tracking moved from top-level `run_id` (which creates a separate API partition) to `metadata.session_id`. New memories land in the default partition and are visible to all queries.
- **`enforce_metadata_defaults.sh` no longer injects `run_id`:** The hook was appending `{"run_id": "*"}` to every `search_memories` and `get_memories` filter, which broke both endpoints. Removed entirely — identity injection (`user_id`/`app_id`) still works.
- **`_search.py` simplified:** Removed `run_id: "*"` from search payload. Uses plain `user_id` + `app_id` filters.
- **`auto_import.py` delete endpoint 404:** Stale chunk deletion used `DELETE /v3/memories/{id}/` which returns 404 (v3 is ADD-only). Changed to `DELETE /v1/memories/{id}/`.
- **Banner count accurate:** `on_session_start.sh` count query uses `user_id` + `app_id` filters without `run_id`. Shows total count only (removed noisy auto-import breakdown).
- **`quickstart.md` wrong add endpoint:** cURL example used `POST /v1/memories/` (v1 add is removed). Fixed to `POST /v3/memories/add/`.
- **Session stats always 0:** PostToolUse hooks never fire for plugin MCP tools (confirmed via debug logs — only SessionStart, UserPromptSubmit, PreToolUse, and Stop fire). Moved session stats tracking (`session_stats.py add/search`) into `enforce_metadata_defaults.sh` (PreToolUse), which does fire on every MCP tool call.
- **Periodic nudge never firing:** Message count file used session UUID in filename (`/tmp/mem0_msg_count_${SESSION_ID}`) which was cleared on session start. Changed to `$USER`-keyed filename, matching the session stats file convention.
- **`/mem0:stats` session query returning 0:** Stats skill attempted API queries with `run_id` and `metadata.session_id` filters that return empty results. Session stats now come exclusively from the local stats file (which is accurate now that PreToolUse tracks adds).
- **Auto-capture stops working mid-session:** After the initial rubric injection (first message), subsequent messages got zero context from the UserPromptSubmit hook. The banner instruction to "proactively store learnings" fades as conversation grows and Claude forgets. Two-pronged fix: (1) **Direct API auto-capture hook** (`auto_capture.py`): every 3rd message, `on_user_prompt.sh` spawns a background Python script that reads the last 3 exchanges from the transcript JSONL and sends them directly to `POST /v3/memories/add/` with `infer=True`. No reliance on Claude calling `add_memory`. (2) **Proportional prompt nudge** as fallback: starting from 3rd message, if Claude has stored fewer than 1 memory per 3 messages, a brief "store learnings via add_memory" directive is injected.
- **Desktop app: API key not found:** Claude Code Desktop does not inherit shell environment variables — only `PATH` is read from shell profiles. Users who set `export MEM0_API_KEY=m0-...` in `~/.zshrc` or `~/.bashrc` got "Setup Required" on Desktop while CLI worked fine. Added grep-based shell profile extraction as a 4th fallback in both `_identity.sh` (bash) and `_identity.py` (Python). Scans `~/.zshrc`, `~/.bashrc`, `~/.zprofile`, `~/.bash_profile`, `~/.profile` for `MEM0_API_KEY=` assignments. Skips variable references (`$OTHER_VAR`), commented-out lines, and strips quotes/inline comments.
- **Desktop app: zero memories added over multi-day usage:** Agent never proactively called `add_memory` — only `search_memories` and `get_all`. Root cause: session banner instruction was passive ("before finishing a session, store learnings") and easily ignored. No mechanism existed to re-prompt the agent mid-session. Fixed with a periodic nudge in `on_user_prompt.sh`: every 5th substantial message, the hook checks `session_stats` for add count; if fewer than 2 memories stored, injects a directive into Claude's context via `additionalContext` telling it to store learnings immediately. Counter resets on session start.
- **Setup Required banner missing Desktop instructions:** Updated no-API-key banner with Desktop-specific setup paths: `claude plugin configure mem0`, Desktop app environment editor (Settings > Environment), and CLI `export` as fallback.

### Removed

- **Stop hook (all 3 editors):** Removed from `hooks.json`, `cursor-hooks.json`, `codex-hooks.json`. Deleted `on_stop.sh`, `on_stop_cursor.sh`, `on_stop_codex.sh`, `stop_hook_check.py`. The Stop hook could not reliably feed context back to Claude (command-type hooks' `reason` field is user-facing only, not injected into Claude's context). Auto-capture handled by PreCompact hook instead.
- **SessionEnd hook:** Removed from `hooks.json`. Deleted `on_session_end.sh`. Redundant with PreCompact auto-capture.
- **5 redundant hook scripts:** `on_git_commit_capture.sh` (fired on every Bash command containing "git"), `on_post_commit.sh` (fired on every Bash command), `on_task_completed.sh`, `on_post_compact.sh`, `on_subagent_stop.sh`. These were already removed from Claude's `hooks.json` in v0.2.5 but script files remained on disk. Also removed `on_post_commit.sh` references from `cursor-hooks.json` and `codex-hooks.json`.
- **Dead settings:** Removed `output_style`, `skip_tools`, `capture_tools` from `load_settings.py` defaults. The `output-styles/` directory and `on_tool_failure.sh` script were already deleted.
- **`test_on_file_read.py`:** Removed test file for deleted `on_file_read.sh` hook.

### Changed

- **`/mem0:stats` lifetime query:** Single `get_memories` call with `user_id` + `app_id` filters (no `run_id`).
- **`/mem0:tour` full fetch:** Single `get_memories` call with `user_id` + `app_id` filters (no `run_id`).
- **API key resolution order (4 fallbacks):** `MEM0_API_KEY` env var > `CLAUDE_PLUGIN_OPTION_API_KEY` (plugin configure) > `CLAUDE_PLUGIN_OPTION_MEM0_API_KEY` (legacy userConfig) > shell profile extraction. Applies to both `_identity.sh` and `_identity.py`.
- **Session start banner:** Proactive memory instruction changed from passive "before finishing a session" to active "proactively store learnings incrementally as work progresses. Do NOT wait until the session ends."
- **Message counter on session start:** `on_session_start.sh` now resets `/tmp/mem0_msg_count_*` files to ensure nudge counter starts fresh each session.

## 0.2.5

### Fixed

- **PostToolUse field name: `tool_output` → `tool_response`:** All three PostToolUse scripts (`on_bash_output.sh`, `on_post_commit.sh`, `on_post_tool_use.sh`) were reading `.tool_output` from stdin JSON — a field that never existed in the Claude Code hooks spec. The correct field is `.tool_response` (confirmed via official docs at code.claude.com/docs/en/hooks). This was silently `null` on every invocation, meaning bash error detection and post-commit checks never actually fired.
- **Stop hook invalid `hookSpecificOutput`:** `on_stop.sh` returned `hookSpecificOutput` with `hookEventName: "Stop"` — but `Stop` is not a valid `hookEventName` discriminant. Claude Code rejected the JSON with "Hook JSON output validation failed". Replaced with spec-compliant `{ decision: "block", reason: "..." }`.
- **SessionStart banner invisible:** Switched from JSON `hookSpecificOutput.additionalContext` (discrete/hidden system reminder) back to raw text `cat <<BANNER` (shown directly in transcript). Per official docs, raw stdout from SessionStart hooks is visible context; `additionalContext` is not.
- **`Write|Edit` matcher missing `MultiEdit`:** `block_memory_write.sh` could be bypassed via `MultiEdit` tool. Matcher now `Write|Edit|MultiEdit`.
- **PreToolUse MCP matcher coverage gap:** `enforce_metadata_defaults.sh` not triggered for `get_memory` or `update_memory`. Added 4 tool name variants.
- **`capture_compact_summary.py` never called:** `on_session_start.sh` compact branch never spawned it. Post-compaction summaries were not stored. Added background spawn.
- **Unguarded variables under `set -u` in `on_session_start.sh`:** Bare `${MEM0_RESOLVED_USER_ID}` etc. without `:-` fallbacks. Script died silently if `_identity.sh` failed to source. All references now use `${VAR:-default}`.
- **`enforce_metadata_defaults.sh` silent failure on jq error:** Final `jq -n --argjson` had no error guard under `set -euo pipefail`. Added `|| true`.
- **Single-quote injection in `on_git_commit_capture.sh`:** Shell variables interpolated via `'$VAR'` inside `python3 -c`. Filenames with `'` broke Python syntax. Replaced with `os.environ.get()`.
- **Identity injection on `add_memory` (`enforce_metadata_defaults.sh`):** Hook now sources `_identity.sh` and injects `user_id` and `app_id` as top-level params when the agent omits them. Prevents orphaned memories with null scoping that were invisible to filtered queries. Root cause of onboarding writes landing with `user_id=null, app_id=null`.
- **Identity injection on `search_memories` and `get_memories`:** Hook now intercepts these tools and injects `user_id`/`app_id` into `filters.AND[]` when missing. Handles three filter states: no filters (creates from scratch), flat filters (converts to AND format), existing AND array (appends missing clauses). Prevents MCP server from auto-injecting wrong identity.
- **Identity injection on `delete_all_memories`:** Hook injects top-level `user_id`/`app_id` to prevent accidental cross-scope deletion.
- **`/mem0:export` incorrect `get_memories` call:** Was passing `user_id`/`app_id` as top-level params; MCP tool only accepts them inside `filters`. Changed to `filters={"AND": [{"user_id": "..."}, {"app_id": "..."}]}`.
- **`/mem0:stats` same `get_memories` issue:** Fixed both lifetime and session stat queries to use `filters` instead of top-level identity params.
- **`/mem0:pin` passes `metadata` to `update_memory`:** MCP `update_memory` tool only accepts `memory_id`, `text`, `source` — no `metadata` param. Pin/unpin now uses `[PINNED]` text prefix marker instead. Also added explicit `user_id`/`app_id` to `add_memory` for new pinned memories.
- **`/mem0:health --deep` ambiguous `get_memories` call:** Clarified identity goes in `filters`, not as top-level params.
- **`/mem0:memory-reviewer` same ambiguity:** Explicit `filters={"AND": [...]}` for `get_memories`.
- **`/mem0:dream` stale artifact:** Removed `(item 15)` from Step 4 heading.
- **`/mem0:dream` contradiction resolution no-op:** `update_memory` on loser with its own text did nothing. Changed to `delete_memory(memory_id=<loser_id>)` to actually remove the losing memory.
- **`/mem0:health` Check 3 `search_memories` top-level `user_id`:** Removed top-level `user_id` param; identity only in `filters.AND[]`. Changed `limit` to `top_k`.
- **`/mem0:health` Check 4 `add_memory` missing `infer=False`:** Health probe wasted LLM tokens on extraction. Added `infer=False`. Also fixed: was expecting `memory_id` in response but v3 returns `event_id`. Now uses `get_event_status` to get memory ID for cleanup.
- **`/mem0:tour` `get_memories` top-level identity:** Both standard and cross-project modes passed `user_id`/`app_id` as top-level params. Moved to `filters.AND[]`.
- **`/mem0:onboard` `search_memories` top-level `user_id`:** Removed extra top-level `user_id` param from connectivity check.
- **`/mem0:context-loader` incomplete filter table:** Filter examples showed only `metadata.type` without `user_id`/`app_id`. Now shows full `AND` filter structure.
- **7 skills used `limit` instead of `top_k` for `search_memories`:** MCP tool param is `top_k`, not `limit`. Fixed in: health, onboard, tour (3 places), switch-project, stats (weekly mode + latency probe).
- **`/mem0:stats` latency probe missing `filters`:** `search_memories` call had no identity filters. Added `user_id`/`app_id` in `filters.AND[]`.

### Added

- **`stop_hook_check.py`:** Pure-stdlib transcript analyzer for the Stop hook. Reads last 500 lines of transcript JSONL, parses tool calls, file modifications, and git commands. Returns `{"should_block": bool, "context": "..."}`. Trivial sessions (< 3 tool calls, no file edits) skip capture entirely.
- **Checklist for `/mem0:dream`:** 6-step progress tracker per Claude skill best practices for complex multi-step workflows.
- **Checklist for `/mem0:onboard`:** 7-step progress tracker for onboarding wizard.
- **Expanded hook matcher (all 3 configs):** `enforce_metadata_defaults.sh` now triggers on `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, and `delete_all_memories` (12 tool name variants covering both MCP naming conventions).

### Changed

- **Stop hook uses MCP-driven capture:** When meaningful work detected and no memories stored, returns `decision: "block"` asking Claude to call `add_memory` via MCP. One-shot flag prevents infinite loops. REST API capture runs in background as fallback.
- **SessionStart banner uses raw text stdout:** Replaced JSON `additionalContext` with `cat <<BANNER` for reliable display per official hooks spec.
- **`enforce_metadata_defaults.sh` rewritten:** Handler-based dispatch for 4 tool types. `add_memory` gets top-level identity + metadata defaults. `search_memories`/`get_memories` get filter identity injection. `delete_all_memories` gets top-level identity. Never overrides explicitly-passed identity.

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
