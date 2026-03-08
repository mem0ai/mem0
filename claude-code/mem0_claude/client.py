"""Client factory with lazy initialization and env loading."""

import os
from pathlib import Path

_client = None


def load_env(cwd=None):
    """Load .env from project root (idempotent)."""
    candidates = []
    if cwd:
        candidates.append(Path(cwd) / ".env")
    # Fallback: walk up from this file
    candidates.append(Path(__file__).resolve().parent.parent.parent.parent / ".env")

    for candidate in candidates:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
            return


def get_client():
    """Create and return a MemoryClient (lazy singleton)."""
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        return None

    from mem0 import MemoryClient

    _client = MemoryClient(
        api_key=api_key,
        org_id=os.environ.get("MEM0_ORG_ID"),
        project_id=os.environ.get("MEM0_PROJECT_ID"),
    )
    return _client


def reset_client():
    """Reset the singleton (for testing or reconfiguration)."""
    global _client
    _client = None
