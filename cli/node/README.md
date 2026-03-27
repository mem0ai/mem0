# mem0 CLI (Node.js)

The official command-line interface for [mem0](https://mem0.ai) — the memory layer for AI agents. TypeScript implementation.

## Prerequisites

- Node.js **18+**
- pnpm (`npm install -g pnpm`)

## Installation

```bash
npm install -g @mem0/cli
```

Or from source:

```bash
cd node
pnpm install
pnpm build
pnpm link --global

# Now use it like a normal CLI
mem0 --help
```

## Running during development

```bash
cd node
pnpm install

# Development mode (runs TypeScript directly, no build needed)
pnpm dev --help
pnpm dev add "test memory" --user-id alice
pnpm dev search "test" --user-id alice

# Or build first, then run the compiled JS
pnpm build
node dist/index.js --help
node dist/index.js add "test memory" --user-id alice
```

## Quick Start

```bash
# Set up your configuration
mem0 init

# Add a memory
mem0 add "I prefer dark mode and use vim keybindings" --user-id alice

# Search memories
mem0 search "What are Alice's preferences?" --user-id alice

# List all memories
mem0 list --user-id alice
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MEM0_API_KEY` | API key (overrides config file) |
| `MEM0_BASE_URL` | API base URL |
| `MEM0_USER_ID` | Default user ID |
| `MEM0_AGENT_ID` | Default agent ID |
| `MEM0_APP_ID` | Default app ID |
| `MEM0_RUN_ID` | Default run ID |
| `MEM0_ENABLE_GRAPH` | Enable graph memory (true/false) |

## License

Apache-2.0
