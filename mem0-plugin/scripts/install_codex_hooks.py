#!/usr/bin/env python3
"""Install Mem0 lifecycle hooks into ~/.codex/hooks.json.

Codex discovers hooks only at ~/.codex/hooks.json or <repo>/.codex/hooks.json,
and has no plugin-host mechanism for auto-wiring hooks from an installed
plugin. This installer reads the template at hooks/codex-hooks.json, rewrites
the ${CODEX_PLUGIN_ROOT} placeholder to the absolute install path of this
plugin, then merges the entries into ~/.codex/hooks.json.

Re-running is idempotent: existing Mem0 entries (identified by the plugin
directory name in the command string) are removed before fresh entries are
added, so upgrades don't leave duplicates.

Usage:
  python3 install_codex_hooks.py            # install or update
  python3 install_codex_hooks.py --uninstall   # remove Mem0 entries

After installing, Codex requires the hooks feature flag in ~/.codex/config.toml:

  [features]
  codex_hooks = true
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent

CODEX_DIR = Path.home() / ".codex"
HOOKS_FILE = CODEX_DIR / "hooks.json"
CONFIG_FILE = CODEX_DIR / "config.toml"

TEMPLATE_FILE = PLUGIN_ROOT / "hooks" / "codex-hooks.json"

# Substring we look for when identifying entries this installer owns.
# Matches the plugin directory name, which stays stable across install paths.
OWNER_MARKER = "mem0-plugin"


def load_template() -> dict:
    raw = TEMPLATE_FILE.read_text()
    raw = raw.replace("${CODEX_PLUGIN_ROOT}", str(PLUGIN_ROOT))
    return json.loads(raw)


def load_existing() -> dict:
    if not HOOKS_FILE.exists():
        return {"hooks": {}}
    try:
        return json.loads(HOOKS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"error: failed to read {HOOKS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)


def is_owned_entry(entry: dict) -> bool:
    for hook in entry.get("hooks", []):
        if OWNER_MARKER in hook.get("command", ""):
            return True
    return False


def strip_owned_entries(config: dict) -> dict:
    hooks = config.get("hooks", {}) or {}
    for event in list(hooks.keys()):
        hooks[event] = [e for e in hooks[event] if not is_owned_entry(e)]
        if not hooks[event]:
            del hooks[event]
    config["hooks"] = hooks
    return config


def merge_template(config: dict, template: dict) -> dict:
    hooks = config.setdefault("hooks", {})
    for event, entries in template.get("hooks", {}).items():
        hooks.setdefault(event, []).extend(entries)
    return config


def write_config(config: dict) -> None:
    CODEX_DIR.mkdir(parents=True, exist_ok=True)
    HOOKS_FILE.write_text(json.dumps(config, indent=2) + "\n")


def feature_flag_enabled() -> bool:
    if not CONFIG_FILE.exists():
        return False
    content = CONFIG_FILE.read_text()
    for line in content.splitlines():
        stripped = line.split("#", 1)[0].strip().replace(" ", "")
        if stripped == "codex_hooks=true":
            return True
    return False


def print_feature_flag_hint() -> None:
    print()
    print("Codex hooks feature flag is not enabled.")
    print(f"Add this to {CONFIG_FILE}:")
    print()
    print("  [features]")
    print("  codex_hooks = true")
    print()
    print("Then restart Codex.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or remove Mem0 Codex hooks.")
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove Mem0 entries from ~/.codex/hooks.json and exit.",
    )
    args = parser.parse_args()

    config = load_existing()

    if args.uninstall:
        config = strip_owned_entries(config)
        write_config(config)
        print(f"Removed Mem0 hooks from {HOOKS_FILE}")
        return 0

    if not TEMPLATE_FILE.exists():
        print(f"error: template not found at {TEMPLATE_FILE}", file=sys.stderr)
        return 1

    template = load_template()
    config = strip_owned_entries(config)
    config = merge_template(config, template)
    write_config(config)

    print(f"Installed Mem0 hooks into {HOOKS_FILE}")
    print(f"Plugin path: {PLUGIN_ROOT}")
    print("Events: SessionStart, UserPromptSubmit, Stop")

    if not feature_flag_enabled():
        print_feature_flag_hint()

    return 0


if __name__ == "__main__":
    sys.exit(main())
