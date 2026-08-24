# Mem0 for Claude Code

Cross-session memory and token savings for coding agents.

## What the plugin does

### Memory

- During a Claude Code session, Mem0 saves small details on your computer:
  user messages, Claude's final answers, changed file paths, and short results
  from test and build commands.
- Mem0 does not save complete files, edited source code, or full tool output by
  default.
- After every five completed exchanges, Mem0 sends that new part of the session
  to Mem0 in the background. A large exchange is sent sooner. Compacting or
  ending the session sends anything that remains. The extraction request contains
  the selected conversation and changed file paths. Test and build command details
  stay on the user's computer unless Claude mentions a conclusion in its visible
  response. Mem0 creates memories that may help with later work in the same
  repository.
- Before Claude's first response in a later session, Mem0 searches with the
  user's prompt and supplies up to five memories. Claude can call
  `search_memories` afterward to ask another specific question; users can make
  the same search with `/mem0:search`. Those searches return at most three
  memories by default. All returned memory context is capped at 4,000
  characters. Mem0 does not rerank results or apply another score cutoff.
- The automatic first-prompt search does not repeat a memory it already supplied
  in that session. Each explicit `search_memories` call runs a fresh search, so
  asking the same question again can return the same memory.
- Claude has no separate command for adding a memory. If you say “remember this”
  or ask Claude to learn a repository for later, that request and Claude's
  findings go through the same memory creation process as the rest of the
  session.

### Sonnet coding agent

- `mem0:sidekick` is a normal Sonnet coding agent with file, search, shell,
  editing, testing, and web tools.
- Claude Code gives it a separate Git worktree and a separate conversation.
- It can investigate, implement, test, debug, or review something instead of an
  Opus or Fable session doing the same work. That can reduce cost when the main
  agent does not repeat the work.
- The main agent reviews the result. Corrections go to the same Sonnet agent, so
  it keeps what it already learned.
- Changes stay in the sidekick's worktree until the main agent reviews and copies
  them into the main checkout.

Mem0 never blocks normal Claude Code work when a hook fails. It does not proxy
Claude traffic, rewrite tool output, edit `CLAUDE.md`, force Claude to use the
sidekick, or change how Claude implements the user's request.

## Install

You need Claude Code and a Mem0 Platform API key.

For a first installation:

```bash
export MEM0_API_KEY='your-mem0-api-key'
claude plugin marketplace add mem0ai/mem0
claude plugin install mem0@mem0-plugins --scope user --config api_key="$MEM0_API_KEY"
unset MEM0_API_KEY
```

If Mem0 is already installed, update it with:

```bash
claude plugin marketplace update mem0-plugins
claude plugin update mem0@mem0-plugins --scope user
```

Restart Claude Code after installing or updating Mem0, then open a Git
repository and work normally.

To remove Mem0:

```bash
claude plugin uninstall mem0@mem0-plugins
```

If you are working on Mem0 itself, you can load the current checkout directly:

```bash
claude --plugin-dir .
```

## Upgrading from 0.2.x

This is a breaking major update to the Claude Code plugin. It replaces the
0.2.x architecture and command set, but nothing about your existing memories
or configuration is lost:

- **Memories carry over automatically.** Mem0 keeps the same user and
  repository scoping the 0.2.x plugin used, including
  `~/.mem0/project_map.json`, so existing memories for a repository stay
  available after upgrading.
- **Environment variables keep working.** `MEM0_API_KEY`, `MEM0_USER_ID`, and
  `MEM0_PROJECT_ID` are still honored.
- **Commands are replaced.** The 0.2.x command set is replaced by
  `/mem0:search`, `/mem0:status`, `/mem0:forget`, `/mem0:pause`,
  `/mem0:resume`, and `/mem0:remember`.
- **The hosted MCP server is replaced.** Its nine read/write tools
  (`add_memory`, `search_memories`, `get_memories`, `get_memory`,
  `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`,
  `list_entities`) are replaced by the single, read-only `search_memories`
  tool described below.
- **Local config files are no longer read.** `~/.mem0/settings.json` and
  per-project `mem0.md` files are ignored.
- **Old memories are still searchable, but not by category.** Normal search
  finds memories created before the upgrade, but the new category filters do
  not find them.

Update with the same commands used for any other update:

```bash
claude plugin marketplace update mem0-plugins
claude plugin update mem0@mem0-plugins --scope user
```

## Use

Work in Claude Code normally. Mem0 saves useful memories when Claude compacts or
ends the session. On the first prompt of a later session, Mem0 searches with
that prompt before Claude begins working. Claude can search again when earlier
work may avoid repeated file reads, searches, or experiments.

You can search directly, optionally choosing the result count or one memory
category:

```text
/mem0:search Why does the ODS serializer keep dates timezone-naive?
/mem0:search What parser failures were fixed? --top-k 5 --category problems_and_fixes
```

Claude decides whether to use the Sonnet coding agent. You can ask for it
directly when you want to test it:

```text
Ask Mem0's sidekick to investigate and implement this in its separate worktree.
Review its result and send any corrections back to the same sidekick.
```

Claude Code normally creates the sidekick's worktree from the repository's
default branch. To create it from the main session's current commit, set
`worktree.baseRef` to `"head"` in the repository's Claude settings. Uncommitted
changes are not copied into the sidekick's worktree.

## Memory search

- `search_memories` lets Claude search memories from earlier sessions in this
  repository with a question, an optional result count from 1 to 20, and an
  optional category.
- `/mem0:search <question>` makes the same search when the user asks directly.
  Add `--top-k 5` to choose the result count. Add `--category project_knowledge`,
  `--category decisions_and_constraints`, `--category workflows`,
  `--category problems_and_fixes`, or `--category results` to search only one
  category. Without this option, Mem0 searches every category.

## Commands

| Command | What it does |
| --- | --- |
| `/mem0:search` | Search memories from earlier Claude Code sessions in this repository. |
| `/mem0:status` | Show whether Mem0 memory is working in this repository — configuration, capture state, pending flushes, and whether the Mem0 API key is valid. |
| `/mem0:forget` | Delete the Mem0 memories stored for this repository (and this user), after confirming with you. |
| `/mem0:pause` | Pause Mem0 memory capture on this machine. |
| `/mem0:resume` | Resume Mem0 memory capture after it was paused with `/mem0:pause`. |
| `/mem0:remember` | Acknowledge a "remember this" request and make sure it is captured well. |

## Requirements

- Python 3.10+ and Git.
- A Claude Code version that supports plugin agents, worktree isolation for
  agents, and the `SubagentStart`, `SubagentStop`, and `PostToolUseFailure`
  hook events.

## Settings

| Setting | Default | What it controls |
| --- | ---: | --- |
| `api_key` | required | Mem0 Platform API key |
| `user_id` | local account name | The user ID used for memories. Set it explicitly to share memories across machines. |
| `top_k` | `3` | Most memories returned by `search_memories` or `/mem0:search`; the automatic first search returns up to five |
| `max_context_chars` | `4000` | Most memory characters returned by one search |

## What is stored and sent

Claude Code stores Mem0's local data in `${CLAUDE_PLUGIN_DATA}`:

- `api-key` contains the configured Mem0 key and is readable only by the local
  user. Mem0 does not print it in logs.
- `evidence.sqlite3` stores small details from sessions and records of memory
  creation and search.
- `pending/` holds sessions waiting to be sent to Mem0. Mem0 retries them after
  an interruption.
- `flush-worker.log` records whether Mem0 created memories successfully.
- `plugin-errors.log` records hook errors without credentials.

Mem0 receives each new block of user messages, Claude's final answers, the
Sonnet agent's final answer, and changed file paths. The Claude session ID keeps the earlier messages and rolling summary
for simultaneous sessions separate. Memory searches still span the user's
earlier sessions in the same Git repository. Complete files and general tool
output stay on your computer.

The Sonnet coding agent uses your existing Claude authentication. It can read,
edit, and run commands in its worktree. Mem0 does not copy those edits into the
main checkout automatically.

## Five-minute memory test

Run this in a disposable or familiar Git repository after installing Mem0:

1. Tell Claude:

   ```text
   Remember for future work that this repository's acceptance marker is cobalt-orchid-731.
   ```

2. End the Claude Code session. Start a new session in the same repository and
   run:

   ```text
   /mem0:search What is the acceptance marker?
   ```

3. Check that the result contains `cobalt-orchid-731`.

Memory creation happens after the session in a background process. If the first
search is empty, wait briefly and try again.

To test the Sonnet agent, give it work that requires investigation or code
changes, then send it a correction. Check that the correction goes to the same
agent and worktree.

## Troubleshooting

- Missing key: reinstall Mem0 with `--config api_key="$MEM0_API_KEY"` while
  `MEM0_API_KEY` is set to a non-empty value.
- `401 Unauthorized`: the configured Mem0 key is invalid or expired.
- No memory immediately after ending a session: memory creation may still be
  running. Wait briefly, then search again.
- Sonnet agent does not start: make sure the current folder is a Git repository
  and your Claude Code version supports plugin agents and worktrees.
- Remove Mem0: `claude plugin uninstall mem0@mem0-plugins`.

## Development checks

Run from `integrations/claude-code-plugin/`:

```bash
python3 -m pytest tests -q
python3 -m ruff check .
claude plugin validate --strict .
```
