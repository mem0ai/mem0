# mem0 CLI

The official command-line interface for [mem0](https://mem0.ai) — the memory layer for AI agents.

## Installation

```bash
pip install mem0-cli
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

## License

Apache-2.0
