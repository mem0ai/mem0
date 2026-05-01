# Mem0 CLI Skill for Claude

Manage memories from the terminal using the [Mem0 CLI](https://docs.mem0.ai/cli). This skill teaches Claude how to use every `mem0` command, flag, and output mode -- for both the Node.js and Python implementations.

## What This Skill Does

When installed, Claude can:

- **Run mem0 commands** correctly in your terminal (add, search, list, get, update, delete, import, config, init, status, entity, event)
- **Construct complex invocations** with the right flags, scoping, filters, and output formats
- **Pipe and script** mem0 commands in shell workflows, CI/CD pipelines, and agent loops
- **Debug issues** like missing API keys, entity scoping conflicts, and async processing delays

## Installation

### CLI (Claude Code, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-cli
```

### Claude.ai

1. Download this `skills/mem0-cli` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "mem0-cli", "source": "https://github.com/mem0ai/mem0/tree/main/skills/mem0-cli"}'
```

## Prerequisites

- A Mem0 Platform API key ([Get one here](https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-mem0-cli-readme))
- **Node.js 18+** or **Python 3.10+**
- Install the CLI:

  ```bash
  # Node.js
  npm install -g @mem0/cli

  # Python
  pip install mem0-cli
  ```

- Set the environment variable:

  ```bash
  export MEM0_API_KEY="m0-your-api-key"
  ```

  Or run `mem0 init` for the interactive setup wizard.

## Quick Start

After installing, just ask Claude:

- "Add a memory for user alice that she prefers dark mode"
- "Search alice's memories for dietary preferences"
- "List all memories and output as JSON"
- "Delete all memories for user bob"
- "Set up mem0 CLI in my CI pipeline"
- "Pipe the output of my script into mem0 add"

## What's Inside

```text
skills/mem0-cli/
├── SKILL.md                          # Skill definition and instructions
├── README.md                         # This file
├── LICENSE                           # Apache-2.0
└── references/                       # Documentation (loaded on demand)
    ├── command-reference.md           # Every command, flag, option, and example
    ├── configuration.md               # Config file, env vars, precedence, init wizard
    └── workflows.md                   # Piping, scripting, CI/CD, agent mode recipes
```

## Links

- [Mem0 Platform Dashboard](https://app.mem0.ai?utm_source=oss&utm_medium=skill-mem0-cli-readme)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 CLI Docs](https://docs.mem0.ai/cli)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)

## Skill Graph

This skill is part of the **Mem0 skill graph** -- three interconnected skills for different interfaces to the Mem0 platform:

| Skill | Purpose | Link |
|-------|---------|------|
| **mem0** | Python/TypeScript SDK, REST API, framework integrations | [local](../mem0/SKILL.md) / [GitHub](https://github.com/mem0ai/mem0/tree/main/skills/mem0) |
| **mem0-cli** (this skill) | Terminal commands for memory operations | [local](./SKILL.md) / [GitHub](https://github.com/mem0ai/mem0/tree/main/skills/mem0-cli) |
| **mem0-vercel-ai-sdk** | Vercel AI SDK provider with automatic memory | [local](../mem0-vercel-ai-sdk/SKILL.md) / [GitHub](https://github.com/mem0ai/mem0/tree/main/skills/mem0-vercel-ai-sdk) |

## License

Apache-2.0
