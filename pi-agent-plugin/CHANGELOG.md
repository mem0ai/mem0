# Changelog

## 0.1.0 (2026-06-09)

Initial release of `@mem0/pi-agent-plugin` — persistent semantic memory for Pi Agent.

### Features

- **Extension entry point** — registers `mem0_memory` tool, 7 slash commands, and auto-capture hooks
- **Agent tool** (`mem0_memory`) — search, add, get_all, delete, delete_all with scoped filters
- **Auto-capture** — extracts and stores memories from conversations on `agent_end`
- **Dream consolidation** — automated memory maintenance: merge duplicates, resolve contradictions, prune stale entries. Gated by session count, time elapsed, and memory count thresholds
- **System prompt injection** — appends `MEMORY_POLICY` to every agent turn via `before_agent_start`
- **4 memory scopes** — project (default), session, user, global
- **10 memory categories** — identity, preferences, goals, projects, decisions, technical, relationships, routines, lessons, work
- **8 skills** — context-loader, remember, search, forget, dream, tour, pin, status
- **Output truncation** — tool results capped at 200 lines / 50KB per Pi docs
- **Signal cancellation** — all tool actions respect `AbortSignal`
- **Session shutdown cleanup** — releases dream lock on `session_shutdown`

### Commands

| Command | Description |
|---------|-------------|
| `/mem0-remember` | Store a memory verbatim (no inference) |
| `/mem0-forget` | Search and delete memories |
| `/mem0-search` | Semantic search across memories |
| `/mem0-tour` | Browse all memories by category |
| `/mem0-dream` | Trigger memory consolidation |
| `/mem0-pin` | Pin a memory to protect from pruning |
| `/mem0-status` | Connection health and diagnostics |
