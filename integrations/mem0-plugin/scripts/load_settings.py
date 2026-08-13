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
    "global_search": False,
    "debug": False,
}


def load_settings() -> dict:
    settings = dict(DEFAULTS)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                user = json.load(f)
        except (json.JSONDecodeError, OSError):
            return settings
        if isinstance(user, dict):
            settings.update({k: v for k, v in user.items() if k in DEFAULTS})
    return settings


def create_default_settings() -> bool:
    """Write the default settings file if absent. Returns True if it was created."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_PATH.exists():
        return False
    with open(SETTINGS_PATH, "w") as f:
        json.dump(DEFAULTS, f, indent=2)
        f.write("\n")
    return True


def unknown_keys() -> list[str]:
    """Keys present in the user's settings file that no code reads."""
    if not SETTINGS_PATH.exists():
        return []
    try:
        with open(SETTINGS_PATH) as f:
            user = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(user, dict):
        return []
    return sorted(k for k in user if k not in DEFAULTS)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        if create_default_settings():
            print(f"Created {SETTINGS_PATH}")
        ignored = unknown_keys()
        if ignored:
            print(f"Ignoring unrecognized settings in {SETTINGS_PATH}: {', '.join(ignored)}")
    else:
        print(json.dumps(load_settings()))
