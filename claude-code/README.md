# mem0 × Claude Code

Long-term memory for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions, powered by [Mem0](https://mem0.ai).

Claude Code forgets everything between sessions. This library fixes that. It hooks into Claude Code's event lifecycle to automatically capture insights and recall relevant context — no manual memory management needed.

## How it works

**Auto-Recall** — Before each prompt, the library searches Mem0 for memories matching the current context and injects them into the conversation.

**Auto-Capture** — After each response, the library sends the assistant's output to Mem0. Mem0 decides what's worth keeping — new facts get stored, stale ones updated, duplicates merged.

Both run silently via Claude Code's [hook system](https://docs.anthropic.com/en/docs/claude-code/hooks). No prompting, no manual calls.

### Short-term vs long-term memory

Memories are organized into two scopes:

- **User (long-term)** — Scoped by `user_id` + `app_id`. Persists across all sessions. Contains architectural decisions, implementation patterns, user preferences, and project knowledge.

- **Session (short-term)** — Scoped by `run_id`. Contains context specific to the current conversation. Auto-recalled alongside long-term memories.

During recall, both scopes are searched and deduplicated, then presented separately so the agent has full context.

## Setup

### 1. Install the mem0 SDK

```bash
pip install mem0ai
```

### 2. Configure environment

Add to your project's `.env`:

```bash
MEM0_API_KEY=your-api-key      # From https://app.mem0.ai
MEM0_ORG_ID=your-org-id        # Optional
MEM0_PROJECT_ID=your-project-id # Optional
```

### 3. Create a project config

Create `scripts/mem0_config.py` in your project:

```python
import sys
from pathlib import Path

# Point to the central library
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "mem0" / "claude-code"))

from mem0_claude.types import ProjectConfig

CONFIG = ProjectConfig(
    user_id="your-username",
    app_id="your-project-name",
    custom_instructions="""
Extract and retain:
- Key decisions and their reasoning
- Implementation patterns and conventions
- Bug patterns, root causes, and fixes
- User preferences for workflow and tools

Exclude:
- Raw code blocks longer than 10 lines
- API keys, secrets, credentials
- Recalled memories being re-injected
""",
    custom_categories=[
        {"architecture": "System design decisions and component relationships"},
        {"implementation": "Code patterns, conventions, and build configuration"},
        {"debugging": "Bug patterns, root causes, and fixes"},
        {"preferences": "User preferences, tooling choices, workflow"},
    ],
)
```

### 4. Create hook shims

Each hook is a small Python script that reads JSON from stdin and writes JSON to stdout. Here's the minimal set:

**`scripts/mem0_hook_capture.py`** (Stop hook):
```python
#!/usr/bin/env python3
import json, sys
from mem0_config import CONFIG
from mem0_claude.capture import handle_stop
from mem0_claude.client import load_env

def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        json.dump({"decision": "approve"}, sys.stdout)
        return
    load_env(hook_input.get("cwd", ""))
    try:
        handle_stop(hook_input, CONFIG)
    except Exception as exc:
        print(f"mem0 capture error: {exc}", file=sys.stderr)
    json.dump({"decision": "approve"}, sys.stdout)

if __name__ == "__main__":
    main()
```

**`scripts/mem0_hook_recall.py`** (UserPromptSubmit + SessionStart):
```python
#!/usr/bin/env python3
import json, sys
from mem0_config import CONFIG
from mem0_claude.client import load_env
from mem0_claude.recall import recall, recall_session_start

def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)
    event = hook_input.get("hook_event_name", "")
    load_env(hook_input.get("cwd", ""))
    try:
        if event == "UserPromptSubmit":
            context = recall(hook_input, CONFIG)
        elif event == "SessionStart":
            context = recall_session_start(hook_input, CONFIG)
        else:
            sys.exit(0)
    except Exception:
        sys.exit(0)
    if not context:
        sys.exit(0)
    json.dump({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}, sys.stdout)

if __name__ == "__main__":
    main()
```

### 5. Register hooks

Add to your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "startup|compact|resume",
      "hooks": [{"type": "command", "command": "python3 scripts/mem0_hook_recall.py", "timeout": 15000}]
    }],
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "python3 scripts/mem0_hook_recall.py", "timeout": 15000}]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "python3 scripts/mem0_hook_capture.py", "timeout": 15000}]
    }]
  }
}
```

### 6. Apply project settings

```bash
python3 cli.py --config scripts/mem0_config.py --cwd /path/to/project configure
```

## All supported hooks

| Hook Event | Purpose | Handler |
|------------|---------|---------|
| `SessionStart` | Recall broad project context at session start | `recall_session_start()` |
| `UserPromptSubmit` | Recall prompt-relevant memories | `recall()` |
| `SubagentStart` | Inject context into subagents before they start | `recall_subagent_start()` |
| `Stop` | Capture insights from assistant response | `handle_stop()` |
| `SubagentStop` | Capture deep analysis from subagents | `handle_subagent_stop()` |
| `PreCompact` | Preserve context before compression (7-day expiry) | `handle_pre_compact()` |
| `SessionEnd` | Final capture on Ctrl+C / session close | `handle_session_end()` |

## Features used

| Feature | Status | Notes |
|---------|--------|-------|
| Custom instructions | Per-request | Domain-specific extraction rules |
| Custom categories | Per-request | Project-specific memory tags |
| Graph memory | Enabled | Entity-relationship graphs on all captures |
| Dual-scope search | Active | Long-term + session with deduplication |
| Keyword search + reranking | Active | Hybrid retrieval on all recalls |
| Context stripping | Active | Prevents feedback loops via XML tag removal |
| Tiered expiration | Active | 7-day (compact), 30-day (auto), permanent (seeds) |
| Immutable memories | Seed command | Foundational facts that never change |
| Metadata tagging | Active | Source, capture type, session ID |
| v2 API + v1.1 output | Active | Latest extraction engine and response format |

## CLI

```bash
# Apply project settings
python3 cli.py --config mem0_config.py --cwd /path/to/project configure

# Verify settings
python3 cli.py --config mem0_config.py --cwd /path/to/project verify

# Show memory stats
python3 cli.py --config mem0_config.py --cwd /path/to/project stats

# Search memories
python3 cli.py --config mem0_config.py --cwd /path/to/project search "model routing"

# Query graph relationships
python3 cli.py --config mem0_config.py --cwd /path/to/project graph "architecture"

# Export all memories
python3 cli.py --config mem0_config.py --cwd /path/to/project export

# Clean up duplicates (dry run)
python3 cli.py --config mem0_config.py --cwd /path/to/project cleanup

# Set expiration on auto-captured memories
python3 cli.py --config mem0_config.py --cwd /path/to/project batch-expire 30
```

## Architecture

```
claude-code/
├── cli.py                 ← Management CLI (14 commands)
├── example_config.py      ← Example project configuration
└── mem0_claude/
    ├── __init__.py         ← Public API exports
    ├── types.py            ← ProjectConfig dataclass (all tunable settings)
    ├── client.py           ← Lazy singleton MemoryClient factory
    ├── strip.py            ← Context stripping (feedback loop prevention)
    ├── capture.py          ← Unified capture engine (Stop, SubagentStop, PreCompact, SessionEnd)
    └── recall.py           ← Dual-scope recall engine (UserPromptSubmit, SessionStart, SubagentStart)
```

The library is designed to be imported by thin hook shims in each project. Each project provides its own `ProjectConfig` with domain-specific instructions, categories, and entity scoping. The library handles all mem0 API interaction, context formatting, and error handling.

## License

Apache 2.0
