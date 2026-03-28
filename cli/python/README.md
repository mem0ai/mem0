# mem0 CLI

The official command-line interface for [mem0](https://mem0.ai) — the memory layer for AI agents.

## Installation

### Using pipx (recommended)

```bash
pipx install mem0-cli
```

### Using pip

```bash
pip install mem0-cli
```

> **Note:** On macOS with Homebrew Python, `pip install` outside a virtual environment will fail with an `externally-managed-environment` error ([PEP 668](https://peps.python.org/pep-0668/)). Use `pipx` instead, or install inside a virtual environment.

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
