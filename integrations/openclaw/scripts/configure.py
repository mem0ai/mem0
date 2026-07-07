#!/usr/bin/env python3
"""Patch ~/.openclaw/openclaw.json with skills-mode settings."""

import json
import os
import shutil
import sys


def main():
    api_key = os.environ.get("MEM0_API_KEY", "")
    user_id = os.environ.get("MEM0_USER_ID", os.environ.get("USER", "default"))
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")

    if not api_key:
        print("Error: MEM0_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found. Run 'openclaw configure' first.", file=sys.stderr)
        sys.exit(1)

    # Backup original config
    backup_path = config_path + ".pre-skills-backup"
    if not os.path.exists(backup_path):
        shutil.copy2(config_path, backup_path)
        print(f"  Backed up config to {backup_path}")
    else:
        print(f"  Backup already exists at {backup_path}")

    with open(config_path) as f:
        cfg = json.load(f)

    # 1. Tools profile = full (exposes plugin tools to the model)
    cfg["tools"] = {"profile": "full"}

    # 2. Disable built-in session-memory hook
    cfg.setdefault("hooks", {}).setdefault("internal", {}).setdefault("entries", {})
    cfg["hooks"]["internal"]["entries"]["session-memory"] = {"enabled": False}

    # 3. Plugin config with skills enabled
    entries = cfg.setdefault("plugins", {}).setdefault("entries", {})
    entries["openclaw-mem0"] = {
        "enabled": True,
        "config": {
            "apiKey": api_key,
            "userId": user_id,
            "skills": {
                "triage": {"enabled": True},
                "recall": {
                    "enabled": True,
                    "tokenBudget": 1500,
                    "rerank": True,
                    "keywordSearch": True,
                    "identityAlwaysInclude": True,
                },
                "dream": {"enabled": True},
                "domain": "companion",
            },
        },
    }

    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)

    print("  Config updated:")
    print("    tools.profile = full")
    print("    session-memory = disabled")
    print(f"    skills = enabled (user: {user_id}, domain: companion)")


if __name__ == "__main__":
    main()
