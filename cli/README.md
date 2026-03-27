# mem0 CLI

The official command-line interface for [mem0](https://mem0.ai) — the memory layer for AI agents.

This is a polyglot monorepo providing the mem0 CLI in multiple languages with a shared specification for consistency.

## Repository Structure

```
.
├── cli-spec.json       # Shared CLI specification (source of truth for commands, options, API)
├── python/             # Python implementation (Typer + Rich + httpx)
└── node/               # TypeScript implementation (Commander.js + chalk + native fetch)
```

## Implementations

| Language | Directory | Install | Docs |
|----------|-----------|---------|------|
| Python | [`python/`](./python/) | `pip install mem0cli` | [README](./python/README.md) |
| TypeScript | [`node/`](./node/) | `npm install -g mem0cli` | [README](./node/README.md) |

Both implementations provide identical CLI behavior — same commands, same options, same output formats.

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

## Shared Specification

The `cli-spec.json` file defines the complete CLI surface — all commands, arguments, options, API endpoints, branding constants, and config schema. Both implementations use this as the source of truth for conformance testing.

## License

Apache-2.0
