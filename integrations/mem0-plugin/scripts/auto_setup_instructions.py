#!/usr/bin/env python3
"""Auto-configure mem0's memory-extraction policy (custom_instructions) in the background.

Runs from the SessionStart hook (startup only), exactly like auto_setup_categories.py.
Where categories tune *how memories are tagged*, custom_instructions tune *what mem0
extracts and stores in the first place* — the team's memory policy, e.g. "Remember
architectural decisions, conventions, and preferences; ignore transient debugging and
secrets." It is applied at the mem0 *project* level, so every write honours it: the
model-driven ``add_memory`` MCP calls and the plugin's own hook writes alike.

The policy is sourced (first non-empty wins) from:
  1. the ``MEM0_CUSTOM_INSTRUCTIONS`` environment variable, then
  2. the ``custom_instructions`` field in ``~/.mem0/settings.json``.
An empty policy is a no-op: the project's existing instructions are left untouched.

Design (mirrors auto_setup_categories.py):
  - Resolve the API key; do nothing if it is absent.
  - Gate on a state file (``~/.mem0/instructions_setup.json``) keyed by a hash of the
    API key -> a hash of the policy text, so this only runs once per account and
    re-runs only when the policy text changes.
  - Hold a lock file so concurrent sessions don't race.
  - Reuse the proven SDK path (``client.project.update``) via the plugin venv.
  - Always exit 0; log to stderr only. Must never block a session.

Requires MEM0_API_KEY (or CLAUDE_PLUGIN_OPTION_API_KEY) and the mem0ai SDK, which
ensure_deps.sh installs into ${CLAUDE_PLUGIN_DATA}/venv on session start.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
# Make the mem0ai SDK importable under system python3, mirroring setup_coding_categories.py.
_data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", os.path.join(os.path.expanduser("~"), ".mem0", "plugin-data"))
_venv_site = os.path.join(_data_dir, "venv", "lib")
if os.path.isdir(_venv_site):
    for _d in sorted(os.listdir(_venv_site)):
        _sp = os.path.join(_venv_site, _d, "site-packages")
        if os.path.isdir(_sp) and _sp not in sys.path:
            sys.path.insert(1, _sp)

from _identity import resolve_api_key  # noqa: E402
from load_settings import load_settings  # noqa: E402

log = logging.getLogger("mem0-auto-instructions")
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("[mem0-auto-instructions] %(message)s"))
log.addHandler(_handler)

if os.environ.get("MEM0_DEBUG"):
    _log_dir = os.path.expanduser("~/.mem0")
    try:
        os.makedirs(_log_dir, exist_ok=True)
        _file_handler = logging.FileHandler(os.path.join(_log_dir, "hooks.log"))
        _file_handler.setFormatter(logging.Formatter("[mem0-auto-instructions] %(asctime)s %(message)s"))
        log.addHandler(_file_handler)
    except OSError:
        pass

STATE_FILE = os.path.expanduser("~/.mem0/instructions_setup.json")
LOCK_FILE = os.path.expanduser("~/.mem0/instructions_setup.lock")


# --------------------------------------------------------------------------- #
# Policy source                                                                #
# --------------------------------------------------------------------------- #
def resolve_instructions() -> str:
    """Return the configured extraction policy, env taking precedence over settings."""
    env_value = os.environ.get("MEM0_CUSTOM_INSTRUCTIONS")
    if env_value and env_value.strip():
        return env_value.strip()
    try:
        settings_value = load_settings().get("custom_instructions", "")
    except Exception:
        settings_value = ""
    return settings_value.strip() if isinstance(settings_value, str) else ""


# --------------------------------------------------------------------------- #
# Fingerprints                                                                 #
# --------------------------------------------------------------------------- #
def instructions_fingerprint(instructions: str) -> str:
    """Stable 16-hex digest of the policy text (whitespace-normalised)."""
    normalised = " ".join(instructions.split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]


def apikey_fingerprint(api_key: str) -> str:
    """Opaque 16-hex digest of the API key. Never stores the key itself."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# State file                                                                   #
# --------------------------------------------------------------------------- #
def load_state(path: str = STATE_FILE) -> dict:
    """Load the apikey-fingerprint -> instructions-fingerprint map; {} on any error."""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict, path: str = STATE_FILE) -> None:
    """Persist the state map, creating the parent directory if needed."""
    parent = os.path.dirname(path)
    if parent:
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            log.warning("Could not create state dir: %s", e)
            return
    try:
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        log.warning("Could not save instructions state: %s", e)


def is_applied(state: dict, key_fp: str, instr_fp: str) -> bool:
    """True only when this API key has already had this exact policy applied."""
    return state.get(key_fp) == instr_fp


# --------------------------------------------------------------------------- #
# SDK interaction (client injected for testability)                            #
# --------------------------------------------------------------------------- #
def make_client():
    """Construct a MemoryClient. Imported lazily so this module loads without the SDK."""
    from mem0 import MemoryClient

    return MemoryClient()


def fetch_current_instructions(client) -> str | None:
    """Return the project's current custom_instructions, or None if unavailable."""
    current = client.project.get(fields=["custom_instructions"])
    if isinstance(current, dict):
        value = current.get("custom_instructions")
        return value if isinstance(value, str) else None
    return None


def apply_instructions(client, instructions: str) -> str:
    """Install the policy if it isn't already in place.

    Returns "already-configured" when the project already matches (no write), or
    "applied" after a successful ``project.update``. Raises on API failure.
    """
    current = fetch_current_instructions(client)
    if current is not None and " ".join(current.split()) == " ".join(instructions.split()):
        return "already-configured"
    client.project.update(custom_instructions=instructions)
    return "applied"


# --------------------------------------------------------------------------- #
# Lock (mirrors auto_setup_categories.py)                                      #
# --------------------------------------------------------------------------- #
def _acquire_lock() -> bool:
    """Try to acquire a file lock. Returns False if another instance is running."""
    try:
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            if time.time() - os.path.getmtime(LOCK_FILE) > 120:
                os.unlink(LOCK_FILE)
                return _acquire_lock()
        except OSError:
            pass
        return False


def _release_lock() -> None:
    try:
        os.unlink(LOCK_FILE)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Entry point                                                                  #
# --------------------------------------------------------------------------- #
def main() -> None:
    instructions = resolve_instructions()
    if not instructions:
        log.debug("No custom_instructions configured; leaving project policy untouched")
        return

    api_key = resolve_api_key()
    if not api_key:
        log.debug("MEM0_API_KEY not set, skipping custom-instructions setup")
        return

    key_fp = apikey_fingerprint(api_key)
    instr_fp = instructions_fingerprint(instructions)

    state = load_state()
    if is_applied(state, key_fp, instr_fp):
        log.debug("Custom instructions already configured for this account (cached); skipping")
        return

    os.environ["MEM0_API_KEY"] = api_key

    try:
        client = make_client()
    except ImportError:
        log.debug("mem0ai SDK not ready yet (venv installing?); will retry next session")
        return
    except Exception as e:
        log.warning("Could not initialise MemoryClient: %s", e)
        return

    try:
        result = apply_instructions(client, instructions)
    except Exception as e:
        log.warning("Could not configure custom instructions: %s", e)
        return

    state[key_fp] = instr_fp
    save_state(state)

    if result == "applied":
        log.info("Applied custom instructions (%d chars)", len(instructions))
    else:
        log.info("Custom instructions already configured")


if __name__ == "__main__":
    if not _acquire_lock():
        log.debug("Another auto_setup_instructions instance is running — skipping")
        sys.exit(0)
    try:
        main()
    except Exception as e:  # never block a session
        log.error("Unexpected error: %s", e)
    finally:
        _release_lock()
    sys.exit(0)
