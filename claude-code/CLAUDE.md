# claude-code — Mem0 Integration Library

Persistent long-term memory for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions, powered by [Mem0](https://mem0.ai).

## What this is

A Python library and hook system that gives Claude Code persistent memory across sessions. It hooks into Claude Code's event lifecycle to automatically capture insights from conversations and recall relevant context before each interaction.

This is the Python equivalent of the `openclaw/` TypeScript plugin — same architecture (auto-recall + auto-capture), same dual-scope memory model, but built for Claude Code's hook system instead of OpenClaw's plugin system.

## Directory structure

```
claude-code/
├── CLAUDE.md              ← You are here
├── README.md              ← User-facing documentation
├── cli.py                 ← Management CLI (14 commands)
├── example_config.py      ← Example project configuration
└── mem0_claude/
    ├── __init__.py         ← Public API (15 exports)
    ├── types.py            ← ProjectConfig dataclass
    ├── client.py           ← Lazy singleton MemoryClient factory
    ├── strip.py            ← Context stripping (feedback loop prevention)
    ├── capture.py          ← Capture engine (4 hook handlers)
    └── recall.py           ← Recall engine (3 hook handlers)
```

## Architecture

### Hook lifecycle

```
SessionStart ──→ recall_session_start() ──→ inject broad project context
UserPromptSubmit ──→ recall() ──→ inject prompt-relevant memories
SubagentStart ──→ recall_subagent_start() ──→ inject context into subagents
Stop ──→ handle_stop() ──→ capture insights from assistant response
SubagentStop ──→ handle_subagent_stop() ──→ capture subagent analysis
PreCompact ──→ handle_pre_compact() ──→ preserve context before compression
SessionEnd ──→ handle_session_end() ──→ final capture on exit
```

### Dual-scope memory

- **Long-term** (`user_id` + `app_id` scoped): Persists across all sessions. Architectural decisions, patterns, preferences.
- **Session** (`run_id` scoped): Current session context. Ephemeral, useful for continuity within a session.

Recall searches both scopes, deduplicates by memory ID, and presents them separately in `<recalled-memories>` tags.

### Feedback loop prevention

Recalled memories injected into context get wrapped in `<recalled-memories>` XML tags. Before capture sends anything to mem0, `strip_recalled_context()` removes these blocks. This prevents mem0 from re-ingesting its own output.

## Key design decisions

1. **`last_assistant_message` only** — Hooks receive the last assistant message directly. No JSONL transcript parsing.
2. **Project config is external** — The library takes a `ProjectConfig` dataclass. Each project defines its own config with custom instructions, categories, and entity scoping.
3. **Always approve, never block** — Capture hooks always return `{"decision": "approve"}`. Memory operations are best-effort and never block the user.
4. **Tiered expiration** — Pre-compact memories expire in 7 days. Auto-captures expire in 30 days (configurable). Seeds and immutable memories never expire.
5. **Graph memory enabled by default** — All captures use `enable_graph=True` and `version="v2"`.

## How to add this to a new project

1. Create a `mem0_config.py` in your project's `scripts/` directory (see `example_config.py`)
2. Copy the hook shim templates from the README
3. Register hooks in `.claude/settings.json`
4. Set `MEM0_API_KEY`, `MEM0_ORG_ID`, `MEM0_PROJECT_ID` in your `.env`
5. Run `python3 cli.py --config scripts/mem0_config.py configure` to apply settings

## Making changes

- **No external dependencies** beyond `mem0` (the SDK). Standard library only otherwise.
- The library must work on Python 3.9+ (matches mem0ai's requirement).
- All hooks read JSON from stdin, write JSON to stdout, and log to stderr.
- Test changes with simulated hook input:
  ```bash
  echo '{"hook_event_name":"Stop","last_assistant_message":"test message here","cwd":"."}' | python3 your_hook.py
  ```

## CLI commands

```
configure    Apply project settings (instructions, categories, graph, retrieval criteria)
verify       Verify project configuration
seed         Seed foundational memories from a project config
stats        Show memory counts by category and source
search       Search memories with advanced retrieval
graph        Query entity-relationship graph
feedback     Rate memory quality (POSITIVE/NEGATIVE/VERY_NEGATIVE)
export       Export all project memories as JSON
expire       Set expiration on a specific memory
history      Show edit history for a memory
summary      AI-generated memory summary
cleanup      Find and remove duplicate/low-quality memories
batch-expire Bulk-expire memories by source
webhooks     Manage webhook notifications
```
