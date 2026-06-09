# Changelog

## 0.1.0 (2026-06-09)

Initial release of `@mem0/pi-agent-plugin` — persistent semantic memory for Pi Agent.

### Features

- **Extension entry point** — registers `mem0_memory` tool, 8 slash commands, and auto-capture hooks
- **Agent tool** (`mem0_memory`) — search, add, get_all, delete, delete_all with scoped filters
- **Auto-capture** — extracts and stores memories from both user and assistant messages on `agent_end`
- **Dream consolidation** — automated memory maintenance: merge duplicates, resolve contradictions, prune stale entries. Gated by session count, time elapsed, and memory count thresholds
- **System prompt injection** — appends `MEMORY_POLICY` to every agent turn via `before_agent_start`
- **Monorepo-aware project scoping** — uses `git rev-parse --show-toplevel` for consistent app_id across subdirectories
- **3 memory scopes** — project (default), session, global
- **10 memory categories** — identity, preferences, goals, projects, decisions, technical, relationships, routines, lessons, work
- **8 skills** — context-loader, remember, search, forget, dream, tour, pin, status
- **Confirmation dialogs** — `/mem0-forget` and `/mem0-pin` ask for confirmation before destructive or mutating actions via `ctx.ui.confirm()`
- **Pin preserves memory ID** — `/mem0-pin` uses `mem0.update()` instead of add+delete, keeping the original UUID
- **Full memory IDs** — all displayed memory references show the complete UUID, not truncated short IDs
- **Dream gate optimization** — `dreamChecked` flag prevents repeated `getAll` API calls when the memory gate fails
- **Output truncation** — tool results capped at 200 lines / 50KB per Pi docs
- **Signal cancellation** — all tool actions respect `AbortSignal`
- **Session shutdown cleanup** — releases dream lock on `session_shutdown`
- **PostHog telemetry** — batched event queue with PII-safe error payloads

### Commands

| Command | Description |
|---------|-------------|
| `/mem0-remember` | Store a memory verbatim (no inference) |
| `/mem0-forget` | Search and delete memories (with confirmation) |
| `/mem0-search` | Semantic search across memories |
| `/mem0-tour` | Browse all memories by category |
| `/mem0-dream` | Trigger memory consolidation |
| `/mem0-pin` | Pin a memory to protect from pruning (preserves ID) |
| `/mem0-scope` | Change default scope for this session |
| `/mem0-status` | Connection health and diagnostics |

### Hooks

| Hook | Purpose |
|------|---------|
| `session_start` | Detect project (git root), resolve session ID, increment dream counter |
| `before_agent_start` | Inject memory policy into system prompt, auto-trigger dream if gates pass |
| `agent_end` | Auto-capture conversation memories, check dream completion |
| `session_shutdown` | Release dream lock, flush telemetry |
