"""Load plugin settings from ~/.mem0/settings.json.

Settings file is user-editable. Missing file or keys fall back to defaults.
"""

from __future__ import annotations

import json
from pathlib import Path

SETTINGS_PATH = Path.home() / ".mem0" / "settings.json"

DEFAULTS = {
    "auto_save": True,
    "auto_search": True,
    "search_limit": 10,
    "retention_session_days": 90,
    "confidence_threshold": 0.3,
    "output_style": "compact",
    "debug": False,
    "skip_tools": ["Read", "Glob", "Grep"],
    "capture_tools": ["Edit", "Write", "Bash"],
}


def load_settings() -> dict:
    settings = dict(DEFAULTS)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                user = json.load(f)
            settings.update({k: v for k, v in user.items() if k in DEFAULTS})
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def create_default_settings() -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, "w") as f:
            json.dump(DEFAULTS, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        create_default_settings()
        print(f"Created {SETTINGS_PATH}")
    else:
        print(json.dumps(load_settings()))
