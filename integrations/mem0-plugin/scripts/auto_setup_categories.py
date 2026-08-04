#!/usr/bin/env python3
"""Auto-configure mem0's coding-category taxonomy in the background.

Runs from the SessionStart hook (startup only), exactly like auto_import.py.
mem0 auto-tags every memory with `categories`; by default that list is
consumer-oriented (food, hobbies, ...), which is useless for code. This script
replaces it with the coding-focused taxonomy defined in
``setup_coding_categories.CODING_CATEGORIES`` so search and retrieval are tuned
for development work — without the user ever being asked during onboarding.

Design (mirrors auto_import.py):
  - Resolve the API key; do nothing if it is absent.
  - Gate on a state file (``~/.mem0/categories_setup.json``) keyed by a hash of
    the API key -> a hash of the taxonomy. Categories are scoped to the mem0
    *project* tied to the API key (NOT to the local repo), so this only needs to
    run once per account, and re-runs only if the taxonomy itself changes.
  - Hold a lock file so concurrent sessions don't race.
  - Reuse the proven SDK path (``client.project.update``) via the plugin venv.
  - Always exit 0; log to stderr only. Must never block a session.

Run with no arguments (background) or in the foreground for onboarding to print
a parseable status line.

Requires MEM0_API_KEY (or CLAUDE_PLUGIN_OPTION_API_KEY) and the mem0ai SDK,
which ensure_deps.sh installs into ${CLAUDE_PLUGIN_DATA}/venv on session start.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Importing setup_coding_categories also injects the plugin venv's site-packages
# onto sys.path (its module-level bootstrap), so ``from mem0 import MemoryClient``
# works even when this script is run with the system python3.
from _identity import resolve_api_key  # noqa: E402
from setup_coding_categories import CODING_CATEGORIES, _categories_match  # noqa: E402

log = logging.getLogger("mem0-auto-categories")
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("[mem0-auto-categories] %(message)s"))
log.addHandler(_handler)

if os.environ.get("MEM0_DEBUG"):
    _log_dir = os.path.expanduser("~/.mem0")
    try:
        os.makedirs(_log_dir, exist_ok=True)
        _file_handler = logging.FileHandler(os.path.join(_log_dir, "hooks.log"))
        _file_handler.setFormatter(logging.Formatter("[mem0-auto-categories] %(asctime)s %(message)s"))
        log.addHandler(_file_handler)
    except OSError:
        pass

STATE_FILE = os.path.expanduser("~/.mem0/categories_setup.json")
LOCK_FILE = os.path.expanduser("~/.mem0/categories_setup.lock")


# --------------------------------------------------------------------------- #
# Fingerprints                                                                 #
# --------------------------------------------------------------------------- #
def categories_fingerprint(categories: list = CODING_CATEGORIES) -> str:
    """Stable, order-independent 16-hex digest of the category taxonomy.

    Reordering the categories yields the same fingerprint; adding, removing, or
    editing a category changes it (so the taxonomy re-applies on upgrade).
    """
    pairs = sorted(
        (str(key), str(value))
        for entry in categories
        if isinstance(entry, dict)
        for key, value in entry.items()
    )
    payload = json.dumps(pairs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def apikey_fingerprint(api_key: str) -> str:
    """Opaque 16-hex digest of the API key. Never stores the key itself."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# State file                                                                   #
# --------------------------------------------------------------------------- #
def load_state(path: str = STATE_FILE) -> dict:
    """Load the apikey-fingerprint -> categories-fingerprint map; {} on any error."""
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
        log.warning("Could not save categories state: %s", e)


def is_applied(state: dict, key_fp: str, cat_fp: str) -> bool:
    """True only when this API key has already had this exact taxonomy applied."""
    return state.get(key_fp) == cat_fp


# --------------------------------------------------------------------------- #
# SDK interaction (client injected for testability)                            #
# --------------------------------------------------------------------------- #
def make_client():
    """Construct a MemoryClient. Imported lazily so this module loads without the SDK."""
    from mem0 import MemoryClient

    return MemoryClient()


def fetch_current_categories(client) -> list | None:
    """Return the project's current custom_categories, or None if unavailable."""
    current = client.project.get(fields=["custom_categories"])
    if isinstance(current, dict):
        return current.get("custom_categories")
    return None


def apply_categories(client, proposed: list = CODING_CATEGORIES) -> str:
    """Install the coding taxonomy if it isn't already in place.

    Returns "already-configured" when the project already matches (no write), or
    "applied" after a successful ``project.update``. Raises on API failure.
    """
    current = fetch_current_categories(client)
    if _categories_match(current, proposed):
        return "already-configured"
    client.project.update(custom_categories=proposed)
    return "applied"


# --------------------------------------------------------------------------- #
# Lock (mirrors auto_import.py)                                                #
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
    api_key = resolve_api_key()
    if not api_key:
        log.debug("MEM0_API_KEY not set, skipping coding-categories setup")
        return

    key_fp = apikey_fingerprint(api_key)
    cat_fp = categories_fingerprint()

    state = load_state()
    if is_applied(state, key_fp, cat_fp):
        log.debug("Coding categories already configured for this account (cached); skipping")
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
        result = apply_categories(client)
    except Exception as e:
        log.warning("Could not configure coding categories: %s", e)
        return

    state[key_fp] = cat_fp
    save_state(state)

    if result == "applied":
        log.info("Applied %d coding categories", len(CODING_CATEGORIES))
    else:
        log.info("Coding categories already configured")


if __name__ == "__main__":
    if not _acquire_lock():
        log.debug("Another auto_setup_categories instance is running — skipping")
        sys.exit(0)
    try:
        main()
    except Exception as e:  # never block a session
        log.error("Unexpected error: %s", e)
    finally:
        _release_lock()
    sys.exit(0)
