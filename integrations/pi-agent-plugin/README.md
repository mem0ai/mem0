# @mem0/pi-agent-plugin

Persistent semantic memory for [Pi Agent](https://pi.dev), powered by [Mem0](https://mem0.ai).

This extension gives Pi Agent long-term memory that persists across sessions, projects, and devices. Memories are automatically captured from conversations and can be searched and managed through slash commands and an agent-accessible tool.

Current package version: `0.3.0`. Shared redaction and lifecycle utilities come from [agent-plugin-core](../agent-plugin-core/README.md); Pi keeps its own tools and scopes.

Sidekick is available only in the [Claude Code plugin](../claude-code-plugin/README.md#sonnet-sidekick-agent).

## Features

- **Automatic memory capture**: works like the Mem0 Claude Code plugin, sending your prompts and Pi's final responses at checkpoints
- **Semantic search**: find memories by meaning, not just keywords
- **Scoped memory**: project, session, or global scope
- **Monorepo-aware**: derives the project from the git remote, consistent across subdirectories
- **Confirmation dialogs**: destructive commands ask before acting
- **6 slash commands**: essential memory management from the command line
- **Agent tool**: `mem0_memory` tool lets the agent search and store memories autonomously

## Setup

### 1. Get an API key

Sign up at [app.mem0.ai](https://app.mem0.ai/dashboard/api-keys) and copy your API key.

### 2. Install

```bash
pi install npm:@mem0/pi-agent-plugin
```

### 3. Configure

Set the API key as an environment variable:

```bash
export MEM0_API_KEY="m0-your-key-here"
```

Or create a config file at `~/.pi/agent/mem0-config.json`:

```json
{
  "apiKey": "m0-your-key-here",
  "userId": "your-username",
  "autoCapture": true,
  "defaultScope": "project",
  "searchThreshold": 0.3
}
```

Environment variables (`MEM0_API_KEY`, `MEM0_USER_ID`) override the config file.

`searchThreshold` (default `0.3`) is the minimum similarity score (0–1) a memory must reach to count as a match for `/mem0-search` and `/mem0-forget`. It is passed to the mem0 search API (along with reranking for higher-precision ordering), so a query with no sufficiently similar memory reports no match instead of returning the closest unrelated memories. Raise it to be stricter; lower it if relevant results are missed.

## Commands

| Command | Description |
|---------|-------------|
| `/mem0-remember <text>` | Store a memory verbatim (no inference) |
| `/mem0-forget <query>` | Search and delete memories (with confirmation) |
| `/mem0-search <query>` | Semantic search across memories |
| `/mem0-tour [scope]` | Browse all memories grouped by category |
| `/mem0-scope <scope>` | Change default scope for this session |
| `/mem0-status` | Connection health, identity, and memory count |

## Skills

The plugin includes 6 skills that guide the agent on how to use each capability:

| Skill | Purpose |
|-------|---------|
| `context-loader` | Search memories when earlier work may already explain the task |
| `remember` | Store facts with category classification |
| `search` | Quick semantic search with compact results |
| `forget` | Delete memories with confirmation |
| `tour` | Full memory walkthrough by category |
| `status` | Health check and diagnostics |

## Memory Scopes

| Scope | Filters | Use case |
|-------|---------|----------|
| `project` | repository `agent_id`, or user + app_id | Default. Project-specific knowledge |
| `session` | user + app_id + run_id | Recall restricted to memories saved with the current session ID |
| `global` | user only | All memories across all your projects |

The project id (`app_id`) comes from your git remote (`owner-repo`), falling back to the repository root's directory name, so every subdirectory of a monorepo shares one memory pool. Project recall also covers the hashed repository `agent_id` that automatic capture writes to.

Global tool operations require `/mem0-scope global` or `defaultScope: "global"` in plugin configuration. A model-supplied `scope` argument cannot enable cross-project access on its own. Empty or wildcard user, project, and session identities are rejected.

## Automatic recall and capture

Recall and capture work like the Mem0 Claude Code plugin, regardless of the default scope selected for explicit commands.

Automatic recall runs once per session, on the first prompt of 20 characters or more. It searches this repository's memories (top 5) and adds them to the system prompt for the rest of the session. Later prompts do not search automatically; the agent can call `mem0_memory` with `action="search"` when earlier work may help.

Automatic capture keeps each session's prompts and Pi's final response to each of them, redacts secrets, and sends them to Mem0 with `infer=true`. It sends them after 5 exchanges, 10 messages, or 40,000 characters, after 5 idle minutes, before compaction, and when the session ends. Mem0 extracts repository facts under a hashed repository `agent_id` and personal facts under your `user_id`, using the same instructions and categories as the Claude Code plugin. The Pi session ID is the `run_id`.

## Memory Categories

Automatic capture uses the Claude Code plugin's coding categories: `project_knowledge`, `decisions_and_constraints`, `workflows`, `problems_and_fixes`, and `results`.

Memories saved with the `mem0_memory` tool or `/mem0-remember` are classified into 10 general-purpose categories:

| Category | Description |
|----------|-------------|
| `identity` | Personal details, background, self-descriptions |
| `preferences` | Likes, dislikes, habits, preferred approaches |
| `goals` | Objectives, aspirations, targets |
| `projects` | Ongoing work, initiatives, areas of focus |
| `decisions` | Choices made, rationale, trade-offs |
| `technical` | Technical knowledge, tools, configurations |
| `relationships` | People, teams, organizations |
| `routines` | Recurring patterns, workflows, schedules |
| `lessons` | Insights learned, mistakes to avoid |
| `work` | Professional context, role, responsibilities |

## Architecture

```
pi-agent-plugin/
├── src/
│   ├── entry.ts          # Extension entry point
│   ├── index.ts          # Barrel exports
│   ├── commands.ts       # 6 slash commands
│   ├── prompt.ts         # System prompt injection (MEMORY_POLICY)
│   ├── types.ts          # Shared interfaces and categories
│   ├── telemetry.ts      # PostHog telemetry (batched, PII-safe)
│   ├── config/           # Config loading (~/.pi/agent/mem0-config.json)
│   ├── memory/           # Tool registration, scoping, formatting
│   └── capture/          # Checkpoint capture of prompts and final responses
├── skills/               # 6 SKILL.md files for Pi Agent
├── tests/                # Vitest unit tests
└── dist/                 # Built output (ESM + DTS)
```

## Development

```bash
pnpm install          # Install dependencies
pnpm run typecheck    # Type check
pnpm run test         # Run tests
pnpm run build        # Build (ESM + declarations)
```

## License

[Apache-2.0](LICENSE)
