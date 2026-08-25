# Mem0 for Claude Code

Cross-session memory for Claude Code, plus a Sonnet sidekick agent for
delegated work.

Claude Code forgets everything between sessions. This plugin fixes that:
hooks save small session details on your computer, a background worker turns
them into Mem0 memories after the session, and Claude automatically gets the
relevant ones back at the start of later sessions in the same repository.

## What the plugin does

### Memory

- During a session, hooks save small details on your computer: user messages,
  Claude's final answers, changed file paths, and short results from test and
  build commands. Complete files, edited source code, and full tool output are
  not saved by default.
- After every five completed exchanges, a background worker sends that new
  part of the session to the Mem0 Platform. A large exchange is sent sooner,
  and compacting or ending the session sends whatever remains. The request
  contains the selected conversation and changed file paths; test and build
  details stay on your computer unless Claude mentions a conclusion in its
  visible response. Mem0 turns each submission into memories that may help
  with later work in the same repository.
- Before Claude's first response in a later session, the plugin searches with
  your prompt and supplies up to five memories. Claude can call the
  `search_memories` tool afterward with another specific question, and you can
  run the same search yourself with `/mem0:search`. Explicit searches return
  at most three memories by default, all returned memory context is capped at
  4,000 characters, and results are not reranked or filtered by another score
  cutoff.
- The automatic first search does not repeat a memory it already supplied in
  that session. Each explicit search runs fresh, so asking the same question
  again can return the same memory.
- There is no separate command for adding a memory. If you say "remember
  this" or ask Claude to learn a repository for later, that request and
  Claude's findings go through the same memory creation process as the rest
  of the session.

### Sonnet sidekick agent

- `mem0:sidekick` is a normal Sonnet coding agent with file, search, shell,
  editing, testing, and web tools.
- Claude Code runs it in a separate Git worktree with its own conversation.
- It can investigate, implement, test, debug, or review something instead of
  an Opus or Fable session doing the same work. That can reduce cost when the
  main agent does not repeat the work.
- The main agent reviews the result. Corrections go back to the same Sonnet
  agent, so it keeps what it already learned.
- Changes stay in the sidekick's worktree until the main agent reviews and
  copies them into the main checkout.

Mem0 never blocks normal Claude Code work when a hook fails. It does not
proxy Claude traffic, rewrite tool output, edit `CLAUDE.md`, force Claude to
use the sidekick, or change how Claude implements the user's request.

## Install

You need:

- Python 3.10+ and Git.
- A Claude Code version that supports plugin agents, worktree isolation for
  agents, and the `SubagentStart`, `SubagentStop`, and `PostToolUseFailure`
  hook events.
- A [Mem0 Platform API key](https://app.mem0.ai/dashboard/api-keys), which
  starts with `m0-`.

For a first installation:

```bash
export MEM0_API_KEY='your-mem0-api-key'
claude plugin marketplace add mem0ai/mem0
claude plugin install mem0@mem0-plugins --scope user --config api_key="$MEM0_API_KEY"
unset MEM0_API_KEY
```

If the plugin is already installed, update it with:

```bash
claude plugin marketplace update mem0-plugins
claude plugin update mem0@mem0-plugins --scope user
```

Restart Claude Code after installing or updating (or run `/reload-plugins`
in an existing session), then open a Git repository and work normally.

To remove the plugin:

```bash
claude plugin uninstall mem0@mem0-plugins
```

If you are working on the plugin itself, load the current checkout directly:

```bash
claude --plugin-dir .
```

## Use

Work in Claude Code normally. Mem0 saves useful memories when Claude compacts
or ends the session. On the first prompt of a later session, Mem0 searches
with that prompt before Claude begins working, and Claude can search again
when earlier work may save repeated file reads, searches, or experiments.

You can search directly, optionally choosing the result count or one memory
category:

```text
/mem0:search Why does the ODS serializer keep dates timezone-naive?
/mem0:search What parser failures were fixed? --top-k 5 --category problems_and_fixes
```

Claude decides whether to use the sidekick. You can ask for it directly when
you want to test it:

```text
Ask Mem0's sidekick to investigate and implement this in its separate worktree.
Review its result and send any corrections back to the same sidekick.
```

Claude Code normally creates the sidekick's worktree from the repository's
default branch. To create it from the main session's current commit, set
`worktree.baseRef` to `"head"` in the repository's Claude settings.
Uncommitted changes are not copied into the sidekick's worktree.

## Commands

| Command | What it does |
| --- | --- |
| `/mem0:search` | Search memories from earlier Claude Code sessions in this repository. Accepts `--top-k <n>` and `--category <name>`. |
| `/mem0:status` | Show whether Mem0 memory is working in this repository: configuration, capture state, pending flushes, and whether the Mem0 API key is valid. |
| `/mem0:forget` | Delete the Mem0 memories stored for this repository (and this user), after confirming with you. |
| `/mem0:pause` | Pause Mem0 memory capture on this machine. |
| `/mem0:resume` | Resume Mem0 memory capture after it was paused with `/mem0:pause`. |
| `/mem0:remember` | Acknowledge a "remember this" request and make sure it is captured well. |

`/mem0:search` and the `search_memories` tool take the same inputs: a
question, an optional result count from 1 to 20, and an optional category.
The categories are `project_knowledge`, `decisions_and_constraints`,
`workflows`, `problems_and_fixes`, and `results`; without one, the search
spans all of them.

## Settings

Four options are set at install time with `--config`; the rest of the
behavior is not tunable.

| Setting | Default | What it controls |
| --- | ---: | --- |
| `api_key` | required | Mem0 Platform API key |
| `user_id` | local account name | The user ID memories are stored under. Set it explicitly to share memories across machines. |
| `top_k` | `3` | Maximum memories returned by `search_memories` or `/mem0:search`; the automatic first search returns up to five |
| `max_context_chars` | `4000` | Maximum memory characters returned by one search |

## What is stored and sent

Claude Code stores Mem0's local data in `${CLAUDE_PLUGIN_DATA}`:

- `api-key` contains the configured Mem0 key and is readable only by the
  local user. Mem0 does not print it in logs.
- `evidence.sqlite3` stores small details from sessions and records of memory
  creation and search.
- `pending/` holds sessions waiting to be sent to Mem0. Mem0 retries them
  after an interruption.
- `flush-worker.log` records whether Mem0 created memories successfully.
- `plugin-errors.log` records hook errors without credentials.
- `telemetry.jsonl` queues anonymous usage events until a background process
  sends them; `telemetry-identity.json` holds the id they are sent under.

Mem0 receives each new block of user messages, Claude's final answers, the
Sonnet agent's final answer, and changed file paths. The Claude session ID
keeps simultaneous sessions' earlier messages and rolling summaries separate.
Memory searches still span the user's earlier sessions in the same Git
repository. Complete files and general tool output stay on your computer.

The Sonnet coding agent uses your existing Claude authentication. It can
read, edit, and run commands in its worktree. Mem0 does not copy those edits
into the main checkout automatically.

## Telemetry

The plugin sends anonymous usage events (which hook ran, how long a memory
update took, how many memories came back, the coarse kind of any failure) so
Mem0 can tell which parts of the plugin are used and which are breaking. Repo
and session identifiers are hashed before they leave your computer. Prompts,
memory text, file paths, tool output, and API keys are never sent.

Events are appended to a local file on the hot path and delivered in batches
by a background process, so no hook ever waits on the network. Turn it off
with:

```bash
export MEM0_TELEMETRY=false
```

## Upgrading from 0.2.x

This is a breaking major update to the Claude Code plugin. Your memories
carry over untouched; your local tuning does not.

- **Memories carry over automatically.** Mem0 keeps the same user and
  repository scoping the 0.2.x plugin used, including
  `~/.mem0/project_map.json`, so existing memories for a repository stay
  available after upgrading.
- **Old memories are still searchable, but not by category.** Normal search
  finds memories created before the upgrade, but the new category filters do
  not find them.
- **Commands are replaced.** The 0.2.x command set is replaced by
  `/mem0:search`, `/mem0:status`, `/mem0:forget`, `/mem0:pause`,
  `/mem0:resume`, and `/mem0:remember`.
- **The hosted MCP server is replaced.** Its nine read/write tools
  (`add_memory`, `search_memories`, `get_memories`, `get_memory`,
  `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`,
  `list_entities`) are replaced by the single, read-only `search_memories`
  tool described above.

### What stops working

The 0.2.x config surface is gone, and nothing warns you about it: the old
settings are simply not read any more. What replaces it is the four
install-time settings above, and nothing else.

- **`~/.mem0/settings.json` is ignored.** Every key it held stops applying:
  `auto_save`, `auto_search`, `search_limit`, `confidence_threshold`,
  `retention_session_days`, `global_search`, `debug`.
- **Per-project `mem0.md` files are ignored,** including their
  `## Instructions`, `## Agent Instructions`, and `## Retention` sections.
- **Most `MEM0_*` environment variables are ignored.** Only `MEM0_API_KEY`,
  `MEM0_USER_ID`, `MEM0_RESOLVED_USER_ID`, and `MEM0_PROJECT_ID` are still
  read. The 0.2.x plugin read 28 others, including `MEM0_AUTO_SAVE`,
  `MEM0_AUTO_SEARCH`, `MEM0_SEARCH_LIMIT`, `MEM0_CONFIDENCE_THRESHOLD`,
  `MEM0_RETENTION_SESSION_DAYS`, `MEM0_GLOBAL_SEARCH`, `MEM0_DEBUG`,
  `MEM0_DREAM`, `MEM0_PREFETCH`, `MEM0_RERANK`, `MEM0_PLATFORM`, and
  `MEM0_APP_ID`. This plugin reads its own `MEM0_CODE_*` variables instead;
  run `/mem0:status` to see what is active. `MEM0_TELEMETRY=false` still
  turns usage telemetry off, as it does everywhere else in Mem0.

Upgrade with the same commands as any other update, listed in
[Install](#install).

## Five-minute memory test

Run this in a disposable or familiar Git repository after installing Mem0:

1. Tell Claude:

   ```text
   Remember for future work that this repository's acceptance marker is cobalt-orchid-731.
   ```

2. End the Claude Code session. Start a new session in the same repository
   and run:

   ```text
   /mem0:search What is the acceptance marker?
   ```

3. Check that the result contains `cobalt-orchid-731`.

Memory creation happens after the session in a background process. If the
first search is empty, wait briefly and try again.

To test the Sonnet agent, give it work that requires investigation or code
changes, then send it a correction. Check that the correction goes to the
same agent and worktree.

## Troubleshooting

- Missing key: reinstall Mem0 with `--config api_key="$MEM0_API_KEY"` while
  `MEM0_API_KEY` is set to a non-empty value.
- `401 Unauthorized`: the configured Mem0 key is invalid or expired.
- No memory immediately after ending a session: memory creation may still be
  running. Wait briefly, then search again.
- Sonnet agent does not start: make sure the current folder is a Git
  repository and your Claude Code version supports plugin agents and
  worktrees.
- Remove Mem0: `claude plugin uninstall mem0@mem0-plugins`.

## Development checks

Run from `integrations/claude-code-plugin/`:

```bash
python3 -m pytest tests -q
python3 -m ruff check .
claude plugin validate --strict .
```
