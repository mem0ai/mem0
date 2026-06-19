# Changelog

All notable changes to the `@mem0/opencode-plugin` will be documented in this file.

## 0.2.0 — Native SDK tools, MCP-free, leaner skill set

### Changed (breaking)

- **Memory tools are now native OpenCode tools** registered via the `@opencode-ai/plugin` `tool()` helper and backed by the `mem0ai` SDK directly. The plugin no longer registers or depends on the remote MCP server (`mcp.mem0.ai`); the bundled `opencode.json` and the regex-based MCP call interception have been removed. Tools: `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`, `list_entities`, plus a `get_event_status` helper for async-write status.
- **Skills load via the `config` hook (`skills.paths`)** instead of being copied into the project's `.opencode/` directory on startup. The `installSkills()` filesystem copy and the `cli.ts` installer (`mem0-opencode` bin) have been removed — install with `opencode plugin @mem0/opencode-plugin`.
- **Trimmed to 9 focused skills** (`context-loader`, `dream`, `forget`, `status`, `search`, `scope`, `pin`, `remember`, `tour`). Removed `import`, `export`, `memory-reviewer`, `mem0` (SDK reference), `list-projects`, `stats`, and `onboard`. The old stateful `switch-project` skill is superseded by the project/session/global scope model and the new `/mem0-scope` skill.

### Added

- **Expanded telemetry to the full shared `plugin.*` schema.** In addition to `plugin.session_start` and `plugin.tool_use`, the plugin now emits `plugin.user_prompt`, `plugin.bash_error`, `plugin.pre_compact`, and `plugin.session_stop`. `tool_use` now fires from inside each native tool. Every event also carries `project_hash` (anonymized `sha256(app_id)`) and `os_version`, matching the editor plugin's `telemetry.py`.
- **Auto-dream — gated automatic memory consolidation** (ported from the pi-agent plugin). When the time (`minHours`, default 24), session-count (`minSessions`, default 5), and memory-count (`minMemories`, default 20) gates all pass, the plugin injects a consolidation protocol so the agent merges duplicates, drops stale/sensitive entries, and rewrites vague ones before answering. A filesystem lock (`~/.mem0/mem0-dream.lock`) prevents concurrent sessions from dreaming at once, and completion resets the gates. Tune via the `dream` block in `~/.mem0/settings.json`; disable with `MEM0_DREAM=false`. Emits `plugin.dream_triggered` / `plugin.dream_completed`.
- **Memory `scope` — per-call parameter and a persistent default.** `search_memories`, `get_memories`, `add_memory`, and `delete_all_memories` accept an optional `scope`: `"project"` (this repo, default), `"session"` (this run, adds `run_id`), or `"global"` (across all the user's projects — `app_id: "*"` for reads, user-wide for writes). The new **`/mem0-scope` skill** views and changes the *default* scope (used when no scope is passed), persisted to `~/.mem0/settings.json` (`default_scope`) and read **fresh on each memory operation** so changes apply immediately — no restart. `add_memory` / `search_memories` / `get_memories` honor the default (an explicit `scope`, `filters`, or `agent_id` still wins; a `project` default preserves prior behavior, including `global_search`).

### Changed

- **`/mem0-status` now reports the active default scope and auto-dream readiness.** It reads `default_scope` from `~/.mem0/settings.json` (falling back to `project`) and shows the auto-dream gate progress (sessions / memories / time vs. thresholds) so it's clear *why* a consolidation hasn't run yet.

### Fixed

- **Skills load in place via `skills.paths` — no copying.** The `config` hook adds the plugin's own `opencode-skills/` directory to OpenCode's `skills.paths`, so OpenCode discovers the skills directly from the linked/installed plugin package (recursive `**/SKILL.md` scan). The `installSkills()` step that copied skills into `~/.config/opencode/skills/` (and the legacy `~/.opencode/skills/`) and its version-marker gating are removed — the plugin no longer writes into those directories or creates `~/.opencode`. The `config` hook still registers the `/mem0-*` slash commands via `config.command`: OpenCode's TUI slash menu is built from `config.command`, and skills on `skills.paths` are available to the agent's skill tool but do not appear as slash commands on their own. Skill dir names are `mem0-<skill>` (matching `^[a-z0-9]+(-[a-z0-9]+)*$`); commands are `/mem0-<skill>`.
- **Robust project-id (`app_id`) detection.** Parsed from the git remote's `owner/repo` — handling https, scp-style ssh, and **custom ssh host aliases** like `git@github.com-work:owner/repo.git` — falling back to the git repo's **root directory name** (not the cwd, which may be a sub-directory or your home dir), then the cwd. Fixes the project showing as your username/home when OpenCode was launched outside the repo root.
- **Auto-dream visibility + robustness.** When auto-dream doesn't fire, the plugin logs the blocking gate (e.g. `auto-dream waiting — memories: 3 < 20`), and `/mem0-status` surfaces the same gate progress. The session-start memory count is parsed defensively (handles both paginated `{count}` and bare-array SDK responses) so the memory gate evaluates correctly.
- **Error-pattern lookup** in `tool.execute.after` no longer issues two identical `mem0.search()` calls; it now performs a single `topK: 6` search.
- Corrected the documented system-prompt hook name from `experimental.chat.system.transform` to the actual `experimental.chat.messages.transform`.

### Safety

- **`delete_all_memories` deliberately ignores the default scope.** Deleting user-wide always requires an explicit `scope="global"`, so raising the default to `global` can never turn a routine cleanup into a cross-project wipe.

## 0.1.3 — File-context injection, session summaries & activity timeline, anonymous telemetry

### Added

- **File-context injection (`tool.execute.before` / Read):** Before the agent reads a file, the plugin searches mem0 for memories referencing that file path and injects prior work as system context. Gates on file size (>= 1,500 bytes). Gives the agent "I've worked on this file before" awareness automatically.
- **Stop hook session summary (`experimental.session.compacting`):** Enhanced session compaction to store a structured `session_summary` memory with `infer=True`, letting the mem0 backend AI extract key facts (request, decisions, learnings, next steps). Previously only stored a raw stats string.
- **SessionStart activity timeline:** The initial memory loading now formats recent memories with type icons (⚖️ decision, 🔴 bug_fix, 🔵 task_learning, etc.) and relative age indicators (2h ago, 1d ago) instead of bare text. Provides a visual "Recent Activity" timeline on first message.
- **PostHog telemetry (`telemetry.ts`):** Anonymous, fire-and-forget usage events. Opt out with `MEM0_TELEMETRY=false`. Only fires when an API key is present; never sends memory content, prompts, or the API key — only an anonymized `sha256(apiKey)[:32]` identity plus event type, platform, and plugin version. Emits the same schema as the Mem0 editor plugin (`plugin.*` events, `source: "plugin"`, `platform: "opencode"`) so OpenCode appears as a `platform` in the shared plugin dashboard. Events: `plugin.session_start` (with memory count) and `plugin.tool_use` (`add` / `search` / `update` / `delete`).

### Changed

- **`experimental.session.compacting` handler:** Now stores `metadata.type=session_summary` with `metadata.source=opencode-stop` instead of `metadata.type=session_state` with `metadata.source=pre-compaction`. Includes a structured prompt that instructs mem0's AI to extract request, decisions, learnings, and next steps.
- **Initial context formatting:** Memories shown on first message now include type icons and age labels for quick scanning.

## 0.1.2 — Automatic coding categories & global search

### Added

- **Auto-configured coding categories:** The plugin now automatically sets up 17 coding categories (e.g. `architecture_decisions`, `api_design`, `security`, `debugging_notes`) on the Mem0 project at startup. Runs in the background on every session start via `autoSetupCategories()`, is fully idempotent, and never blocks initialization. Uses SHA-256 fingerprints of the category list and API key — stored in `~/.mem0/categories_setup.json` — to skip redundant API calls on subsequent sessions.
- **Global search mode (`global_search` setting):** New `global_search` toggle in `~/.mem0/settings.json` (default: `false`). When enabled, all `search_memories` and `get_memories` calls use `{"OR": [{"user_id": "*"}]}` instead of the per-user per-project `AND` filter — returning all memories across all users and all `app_id` scopes. Writes (`add_memory`) still tag with the current `user_id` and `app_id`. Applies to all plugin search paths: initial load, per-message recall, resume detection, error-pattern lookup, and compaction context.
- **`/mem0:switch-project --global` / `--no-global`:** Enables or disables global search via the switch-project skill. Persists to `~/.mem0/settings.json`. No manual config editing needed.
- **`MEM0_GLOBAL_SEARCH` environment variable:** Exported to child shells via the `shell.env` hook (`"true"` or `"false"`).

### Changed

- **Search filters are now dynamic:** All search paths throughout the plugin construct filters based on the `global_search` setting instead of always using `AND [user_id, app_id]`.
- **Resume-context searches broadened:** Resume and error-pattern searches no longer include `metadata.type` sub-filters (`session_state`, `decision`, `anti_pattern`, `bug_fix`), broadening recall.
- **System context message updated:** Informs the model when global search is active (`"Global search is ON — searches return all memories across all users and projects. Writes still use user_id=..., app_id=..."`).
- **`/mem0:onboard` Step 5 is no longer interactive:** Removed the manual category installation prompt. Categories now configure automatically in the background; the onboarding step only verifies status and stores a fallback `project_profile` memory if the background run hasn't finished yet.
- **`/mem0:switch-project` skill expanded:** Description and execution updated to document the `--global` and `--no-global` flags alongside the existing project-name argument.

## 0.1.1

- CI/CD publish flow test (`#5288`).
- Fixed tsconfig, added `publishConfig` and bun lockfile (`#5273`).
- Renamed package to `@mem0/opencode-plugin` (`#5272`).
- Added plugin array to bundled `opencode.json` (`#5271`).

## 0.1.0 — Initial release

- **OpenCode plugin** (`@mem0/opencode-plugin` on npm): Pure TypeScript plugin using the `mem0ai` TS SDK — no Python, no shell scripts. Hooks into all 6 OpenCode events (`chat.message`, `tool.execute.before`, `tool.execute.after`, `experimental.chat.system.transform`, `experimental.session.compacting`, `shell.env`). Features: session start memory loading, per-prompt semantic search, error pattern detection with memory lookup, resume/remember intent detection, auto-capture every 3rd message, periodic save nudges, full metadata defaults injection (confidence, source, type, session_id, files, branch), identity injection for search/get/delete filters, type-filtered error pre-fetch (anti_pattern + bug_fix), pre-compaction memory capture, MEMORY.md write blocking, and secret redaction.
- **16 OpenCode-native skills** bundled in `opencode-skills/`: `context-loader`, `dream`, `export`, `forget`, `health`, `import`, `list-projects`, `mem0` (SDK reference), `memory-reviewer`, `onboard`, `peek`, `pin`, `remember`, `stats`, `switch-project`, `tour`. All skills are pure MCP-tool-based — no Python scripts, no shell scripts, no Claude Code dependencies.
- **Auto-install skills and commands (`installSkills()`):** On plugin load, copies all 16 skills to `.opencode/skills/` and creates command wrapper files in `.opencode/commands/` so they appear in the OpenCode `/` palette.
- **CLI installer (`cli.ts`):** `bunx @mem0/opencode-plugin install` auto-configures plugin and MCP server in `~/.config/opencode/opencode.json`.
