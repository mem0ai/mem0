"""Lightweight environment-flag helpers.

Kept in a separate module so heavyweight modules (memory.py, categorization.py)
can share these helpers without importing each other at startup.
"""

import os


def is_local_only() -> bool:
    """True when the team fail-closed mode is active (``MEM0_LOCAL_ONLY``)."""
    return (os.environ.get("MEM0_LOCAL_ONLY") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )
