"""CLI telemetry — anonymous usage tracking via PostHog.

Sends fire-and-forget events to PostHog by spawning a detached subprocess
(telemetry_sender.py). The parent CLI process exits immediately; the
subprocess handles email resolution, caching, and the HTTP POST.

Disable with: MEM0_TELEMETRY=false
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from typing import Any

POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX"
POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/"


def _is_telemetry_enabled() -> bool:
    val = os.environ.get("MEM0_TELEMETRY", "true").lower()
    return val not in ("false", "0", "no")


def _get_distinct_id() -> str:
    """Return a stable anonymous identifier for the current user.

    Priority: cached user_email (from /v1/ping/) > MD5(api_key) > fallback.
    Matches the SDK pattern in mem0/client/main.py.
    """
    try:
        from mem0_cli.config import load_config

        config = load_config()
        if config.platform.user_email:
            return config.platform.user_email
        if config.platform.api_key:
            return hashlib.md5(config.platform.api_key.encode()).hexdigest()
    except Exception:
        pass
    return "anonymous-cli"


def capture_event(
    event_name: str,
    properties: dict[str, Any] | None = None,
    pre_resolved_email: str | None = None,
) -> None:
    """Fire a PostHog event via a detached subprocess (non-blocking).

    When *pre_resolved_email* is provided (e.g. from an upfront ping
    validation), it is used directly as the PostHog distinct ID and the
    subprocess skips its own ``/v1/ping/`` call.
    """
    if not _is_telemetry_enabled():
        return

    try:
        from mem0_cli import __version__
        from mem0_cli.config import CONFIG_FILE, load_config
        from mem0_cli.state import is_agent_mode

        config = load_config()
        distinct_id = pre_resolved_email or _get_distinct_id()

        payload = {
            "api_key": POSTHOG_API_KEY,
            "distinct_id": distinct_id,
            "event": event_name,
            "properties": {
                "source": "CLI",
                "language": "python",
                "cli_version": __version__,
                "agent_mode": is_agent_mode(),
                "python_version": sys.version,
                "os": sys.platform,
                "os_version": platform.version(),
                "$process_person_profile": False,
                "$lib": "posthog-python",
                **(properties or {}),
            },
        }

        context = {
            "payload": payload,
            "posthog_host": POSTHOG_HOST,
            "needs_email": not distinct_id or "@" not in distinct_id,
            "mem0_api_key": config.platform.api_key or "",
            "mem0_base_url": config.platform.base_url or "https://api.mem0.ai",
            "config_path": str(CONFIG_FILE),
        }

        subprocess.Popen(
            [sys.executable, "-m", "mem0_cli.telemetry_sender", json.dumps(context)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception:
        pass
