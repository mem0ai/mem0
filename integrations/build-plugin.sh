#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_DIR="$SCRIPT_DIR/plugin-core"
TEMPLATE_DIR="$SCRIPT_DIR/plugin-template"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <plugin-dir> [plugin-dir...]"
    echo "Example: $0 claude-code-plugin cursor-plugin codex-plugin"
    exit 1
fi

if [ ! -d "$CORE_DIR" ]; then
    echo "Error: plugin-core/ not found at $CORE_DIR"
    exit 1
fi

for plugin in "$@"; do
    target="$SCRIPT_DIR/$plugin"
    if [ ! -d "$target" ]; then
        echo "Skipping $plugin: directory not found"
        continue
    fi

    dest="$target/core"
    mkdir -p "$dest"
    cp "$CORE_DIR"/*.py "$dest/"
    echo "Bundled plugin-core into $plugin/core/ ($(ls "$dest"/*.py | wc -l | tr -d ' ') files)"

    if [ -d "$TEMPLATE_DIR" ] && [ -L "$target/skills" ]; then
        rm "$target/skills"
        cp -RL "$TEMPLATE_DIR/skills" "$target/skills"
        echo "  Resolved skills/ symlink"
    fi
    if [ -d "$TEMPLATE_DIR" ] && [ -L "$target/agents" ]; then
        rm "$target/agents"
        cp -RL "$TEMPLATE_DIR/agents" "$target/agents"
        echo "  Resolved agents/ symlink"
    fi
    if [ -d "$TEMPLATE_DIR" ] && [ -L "$target/mcp.json" ]; then
        rm "$target/mcp.json"
        cp -L "$TEMPLATE_DIR/mcp.json" "$target/mcp.json"
        echo "  Resolved mcp.json symlink"
    fi
done
