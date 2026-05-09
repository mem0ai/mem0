"""Resolve mem0 user_id with deterministic priority.

Resolution priority:
  1. MEM0_USER_ID env var (explicit override)
  2. ~/.mem0/identity.json cache (pinned to current MEM0_API_KEY fingerprint)
  3. Derived: "mem0-" + sha256(MEM0_API_KEY)[:12]
  4. Fallback: $USER, else "default"

Same MEM0_API_KEY across machines yields the same user_id, which fixes
the "47 user buckets per account" symptom from running on multiple
laptops with different $USER values.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

_CACHE_PATH = os.path.expanduser("~/.mem0/identity.json")


def resolve_user_id() -> str:
    explicit = os.environ.get("MEM0_USER_ID", "").strip()
    if explicit:
        return explicit

    api_key = os.environ.get("MEM0_API_KEY", "").strip()
    if api_key:
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        fingerprint = digest[:8]

        try:
            with open(_CACHE_PATH, "r") as f:
                cached = json.load(f)
            if cached.get("api_key_fingerprint") == fingerprint and cached.get("user_id"):
                return cached["user_id"]
        except (OSError, json.JSONDecodeError):
            pass

        derived = "mem0-" + digest[:12]
        try:
            os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
            with open(_CACHE_PATH, "w") as f:
                json.dump(
                    {
                        "user_id": derived,
                        "source": "api_key",
                        "api_key_fingerprint": fingerprint,
                        "resolved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                    f,
                )
        except OSError:
            pass
        return derived

    return os.environ.get("USER") or "default"
