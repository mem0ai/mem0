"""Resolve the mem0 API base URL and guard all network egress.

Why this exists:
  The plugin's lifecycle hooks historically hardcoded ``https://api.mem0.ai``
  with no override, so there was no way to point them at a self-hosted
  OpenMemory server. This module centralizes base-URL resolution AND adds a
  *fail-closed* egress guard so a team deployment can guarantee that NO data
  ever leaves for the cloud.

Behavior:
  - ``OPENMEMORY_API_BASE`` (or legacy ``MEM0_API_BASE``) overrides the base.
  - ``MEM0_LOCAL_ONLY`` (1/true/yes/on) activates fail-closed mode:
      * If no base is configured, ``resolve_api_base()`` returns "" — callers
        must treat that as "do nothing" (NEVER fall back to the cloud).
      * ``egress_allowed(url)`` returns True ONLY for the configured local
        base host; every other host (``*.mem0.ai``, ``*.posthog.com``, …) is
        refused. This is the in-code guarantee — it does not rely on every
        script being configured correctly.
  - Without ``MEM0_LOCAL_ONLY``, the default base stays ``https://api.mem0.ai``
    so the official cloud behavior is preserved for non-team users.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

_CLOUD_DEFAULT = "https://api.mem0.ai"

# Hosts that are always cloud — refused outright in local-only mode even if a
# misconfiguration somehow let one through.
_CLOUD_SUFFIXES = (".mem0.ai", "mem0.ai", ".posthog.com", "posthog.com")


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def is_local_only() -> bool:
    """True when the team fail-closed mode is active (``MEM0_LOCAL_ONLY``)."""
    return _truthy(os.environ.get("MEM0_LOCAL_ONLY"))


def resolve_api_base() -> str:
    """Resolve the API base URL (no trailing slash).

    Returns "" in local-only mode when no base is configured, so callers
    no-op instead of leaking to the cloud.
    """
    base = (os.environ.get("OPENMEMORY_API_BASE")
            or os.environ.get("MEM0_API_BASE") or "").strip()
    if base:
        base = base.rstrip("/")
        # Fail-closed: in local-only mode, refuse a cloud base even if someone
        # mis-set it. This makes every call site collapse to a no-op at once.
        if is_local_only() and _is_cloud_host(_host(base)):
            return ""
        return base
    if is_local_only():
        return ""  # fail-closed: never fall back to the cloud
    return _CLOUD_DEFAULT


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_cloud_host(host: str) -> bool:
    if not host:
        return False
    return any(host == s.lstrip(".") or host.endswith(s) for s in _CLOUD_SUFFIXES)


def egress_allowed(url: str) -> bool:
    """Whether a network call to ``url`` is permitted.

    Outside local-only mode: always allowed (official behavior).
    In local-only mode: allowed ONLY if the host matches the configured local
    base; known cloud hosts are always refused.
    """
    if not is_local_only():
        return True

    host = _host(url)
    if not host:
        return False
    if _is_cloud_host(host):
        return False

    base = resolve_api_base()
    if not base:
        return False
    return host == _host(base)
