# Mem0 for Claude Code

Persistent cross-session memory for Claude Code, plus a Sonnet sidekick agent for delegated work.

Claude Code forgets everything between sessions. This plugin fixes that: hooks capture session details locally, a background worker turns them into Mem0 memories, and Claude automatically gets the relevant ones back at the start of later sessions.

## Prerequisites

- Python 3.10+ and Git.
- A Claude Code version that supports plugin agents, worktree isolation for agents, and the `SubagentStart`, `SubagentStop`, and `PostToolUseFailure` hook events.
- A [Mem0 Platform API key](https://app.mem0.ai/dashboard/api-keys) (starts with `m0-`).

## Install

```bash
export MEM0_API_KEY='your-mem0-api-key'
claude plugin marketplace add mem0ai/mem0
claude plugin install mem0@mem0-plugins --scope user --config api_key="$MEM0_API_KEY"
unset MEM0_API_KEY
```

Restart Claude Code (or run `/reload-plugins`), then open a Git repository and work normally.

To update:

```bash
claude plugin marketplace update mem0-plugins
claude plugin update mem0@mem0-plugins --scope user
```

To remove:

```bash
claude plugin uninstall mem0@mem0-plugins
```

For local development, load the current checkout directly:

```bash
claude --plugin-dir .
```

## How it works

### Memory

1. **Capture.** Hooks save the main agent's activity locally: user messages, Claude's answers, changed file paths, and short test/build results. No model calls, no blocking. Sidekick output is excluded.

2. **Flush.** After every five completed exchanges, a detached background worker sends that batch to Mem0. Large exchanges flush sooner. Ending or compacting the session flushes anything remaining. If idle, an auto-flush runs after five minutes (configurable with `MEM0_CODE_IDLE_FLUSH_SECONDS`). The worker survives Claude Code exiting.

3. **Extract.** Each flush sends a single `add` call with `agent_id` (the project identity), `user_id` (you), `app_id` (the repository), and `run_id` (the session). Mem0 classifies each extracted memory as either:
   - **Shared project memory** (`agent_id`): one namespace per repo, scoped by `app_id`. Stores conventions, decisions, constraints, working commands, and failed commands with their fixes. Everyone on the repo reads and writes the same pool. Never carries a `user_id`. Directory information is stored in metadata for directory-scoped searches.
   - **Personal memory** (`user_id`): your preferred tools, style, habits, and anything you asked to be remembered. Scoped to the repo by `app_id`. Private to you.

4. **Recall.** On the next session's first prompt, the plugin searches automatically and supplies up to five relevant memories. No model is called to write the query.

After that first search, Claude can call `search_memories` with a specific question, and you can run `/mem0:search` yourself. Explicit searches return up to 3 results by default (configurable to 20), capped at 4,000 characters.

### Sonnet sidekick agent

`mem0:sidekick` is a Sonnet coding agent that runs in a separate Git worktree. It can investigate, implement, test, debug, or review something instead of the main (Opus/Fable) session doing the same work, reducing cost when the main agent doesn't need to repeat it.

The main agent reviews the result. Corrections go back to the same sidekick so it keeps what it learned. Changes stay in the sidekick's worktree until the main agent reviews and copies them over.

Mem0 never blocks normal Claude Code work when a hook fails. It does not proxy Claude traffic, rewrite tool output, edit `CLAUDE.md`, force Claude to use the sidekick, or change how Claude implements the user's request.

## Use

Work in Claude Code normally. Memory is captured and recalled automatically.

```text
/mem0:search Why does the ODS serializer keep dates timezone-naive?
/mem0:search What parser failures were fixed? --top-k 5 --category problems_and_fixes
/mem0:search Do I prefer pnpm or npm? --scope mine
```

To use the sidekick:

```text
Ask Mem0's sidekick to investigate and implement this in its separate worktree.
Review its result and send any corrections back to the same sidekick.
```

By default the worktree branches from the repo's default branch. Set `worktree.baseRef` to `"head"` in your Claude settings to branch from the current commit instead. Uncommitted changes are not copied into the sidekick's worktree.

## Commands

| Command | What it does |
| --- | --- |
| `/mem0:search` | Search memories from earlier sessions. Accepts `--top-k <n>`, `--category <name>`, and `--scope <repo\|dir\|mine>`. |
| `/mem0:status` | Check config, capture state, pending flushes, and API key validity. |
| `/mem0:forget` | Delete your memories for this repo (shared project memory stays unless you pass `--include-project-memory`). |
| `/mem0:pause` | Pause memory capture. |
| `/mem0:resume` | Resume capture after a pause. |
| `/mem0:remember` | Tell Claude to capture something specific in its reply. |

Categories for `--category`: `project_knowledge`, `decisions_and_constraints`, `workflows`, `problems_and_fixes`, `results`.

## Search scope

| Scope | What you get |
| --- | --- |
| `repo` (default) | All project memory across every subdirectory, plus your preferences |
| `dir` | Project memory from the current directory (and children), plus your preferences |
| `mine` | Your personal preferences only |

Set the default with the `search_scope` setting or `MEM0_CODE_SEARCH_SCOPE`. Pass `--run-id <session-id>` to see only what one specific session recorded.

## Settings

| Setting | Default | What it controls |
| --- | --- | --- |
| `api_key` | required | Mem0 Platform API key |
| `user_id` | local account name | User ID for memory storage. Resolved from: setting, `MEM0_CODE_USER_ID`, `MEM0_USER_ID`, `MEM0_RESOLVED_USER_ID`, `$USER`, `%USERNAME%`, then `default`. Set explicitly to share across machines. |
| `top_k` | `3` | Max memories per explicit search (1 to 20) |
| `max_context_chars` | `4000` | Max characters returned per search (1,000 to 10,000) |
| `search_scope` | `repo` | Default scope: `repo`, `dir`, or `mine` |

## What is stored and sent

Local data lives in `${CLAUDE_PLUGIN_DATA}`:

- `api-key`: the configured Mem0 key (readable only by the local user)
- `evidence.sqlite3`: session details and records of memory creation/search
- `pending/`: sessions waiting to be sent to Mem0 (retried after interruption)
- `flush-worker.log`: whether memory creation succeeded
- `plugin-errors.log`: hook errors (no credentials)
- `telemetry.jsonl` / `telemetry-identity.json`: anonymous usage events

Mem0 receives each block of user messages, Claude's answers, the sidekick's answer, and changed file paths. Complete files and general tool output stay on your machine. Values that look like credentials are redacted before anything is sent.

## Telemetry

Anonymous usage events (which hook ran, timing, result counts, failure types) so Mem0 can identify what's used and what's breaking. Repo and session IDs are hashed before leaving your machine. Prompts, memory text, file paths, tool output, and API keys are never sent.

Turn it off:

```bash
export MEM0_TELEMETRY=false
```

## Five-minute memory test

Run this in a Git repository after installing:

1. Tell Claude:
   ```text
   Remember for future work that this repository's acceptance marker is cobalt-orchid-731.
   ```

2. End the session. Start a new one in the same repo and run:
   ```text
   /mem0:search What is the acceptance marker?
   ```

3. Check that the result contains `cobalt-orchid-731`.

Memory creation runs in the background. If the first search is empty, wait a moment and try again.

## Upgrading from 0.2.x

Breaking update. Memories carry over, most local config does not.

- **Memories carry over.** Same user and repo scoping, including `~/.mem0/project_map.json`.
- **Old memories searchable, not by category.** Category filters only work on new memories.
- **Commands replaced.** Old commands replaced by `/mem0:search`, `/mem0:status`, `/mem0:forget`, `/mem0:pause`, `/mem0:resume`, `/mem0:remember`.
- **MCP server replaced.** Nine read/write tools replaced by the single read-only `search_memories` tool.
- **`~/.mem0/settings.json` ignored.** All keys stop applying: `auto_save`, `auto_search`, `search_limit`, `confidence_threshold`, `retention_session_days`, `global_search`, `debug`.
- **Per-project `mem0.md` files ignored.**
- **Most `MEM0_*` env vars ignored.** Only `MEM0_API_KEY`, `MEM0_USER_ID`, `MEM0_RESOLVED_USER_ID`, and `MEM0_PROJECT_ID` are still read. Run `/mem0:status` to see what is active.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Missing key | Reinstall with `--config api_key="$MEM0_API_KEY"` while the var is set. |
| `401 Unauthorized` | API key is invalid or expired. Run `/mem0:status`. |
| No memory after ending a session | Extraction runs in the background. Wait a moment, then search again. |
| Sidekick won't start | Must be in a Git repo with a Claude Code version supporting plugin agents and worktrees. |
| Remove the plugin | `claude plugin uninstall mem0@mem0-plugins` |

## Development checks

Run from `integrations/claude-code-plugin/`:

```bash
python3 -m pytest tests -q
python3 -m ruff check .
claude plugin validate --strict .
```
