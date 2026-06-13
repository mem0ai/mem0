#!/usr/bin/env python3
"""Lightweight fire-and-forget telemetry for the mem0 plugin.

Sends anonymous usage events to PostHog using the same project key and
endpoint as the mem0 Python SDK and CLI. No posthog library dependency —
uses stdlib urllib directly (same pattern as cli/python telemetry_sender.py).

CLI usage (called from hooks as a background subprocess):
  python3 telemetry.py <event_type> [--memory_count=N] [--categories_count=N]
                                    [--error_detected] [--file_paths_detected]
                                    [--source=<src>] [--tool=<name>]

Opt-out: set MEM0_TELEMETRY=false (or 0/no/off) to disable all telemetry.

Never sends: user content, memory content, API keys, raw user/project IDs.
Only sends: event type, platform, plugin version, anonymized hashes, counts.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import urllib.error
import urllib.request


def _load_plugin_version() -> str:
    try:
        plugin_json = os.path.join(os.path.dirname(__file__), "..", ".claude-plugin", "plugin.json")
        with open(plugin_json) as f:
            return json.load(f).get("version", "unknown")
    except (OSError, json.JSONDecodeError, KeyError):
        return "unknown"


PLUGIN_VERSION = _load_plugin_version()

POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX"
POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/"
REQUEST_TIMEOUT = 2

SAMPLE_RATE = 1.0


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _distinct_id() -> str:
    """Stable anonymous ID: SHA-256 of API key if available, else SHA-256 of username."""
    api_key = os.environ.get("MEM0_API_KEY") or os.environ.get("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY") or ""
    if api_key:
        return hashlib.sha256(api_key.encode()).hexdigest()[:32]
    user_id = os.environ.get("MEM0_RESOLVED_USER_ID") or os.environ.get("USER") or "unknown"
    return _sha256(user_id)


def detect_platform() -> str:
    explicit = os.environ.get("MEM0_PLATFORM")
    if explicit:
        return explicit
    if os.environ.get("ANTIGRAVITY_PLUGIN_ROOT"):
        return "antigravity"
    if os.environ.get("PLUGIN_ROOT"):
        return "codex"
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return "claude-code"
    if os.environ.get("CURSOR_PLUGIN_ROOT"):
        return "cursor"
    if os.environ.get("WINDSURF_PLUGIN_ROOT"):
        return "windsurf"
    return "plugin"


def is_enabled() -> bool:
    return os.environ.get("MEM0_TELEMETRY", "true").lower() not in ("false", "0", "no", "off")


def build_posthog_payload(event_name: str, properties: dict | None = None) -> dict:
    project_id = os.environ.get("MEM0_PROJECT_ID") or "unknown"
    return {
        "api_key": POSTHOG_API_KEY,
        "distinct_id": _distinct_id(),
        "event": event_name,
        "properties": {
            **(properties or {}),
            "source": "plugin",
            "platform": detect_platform(),
            "plugin_version": PLUGIN_VERSION,
            "project_hash": _sha256(project_id),
            "os": sys.platform,
            "os_version": platform.version(),
            "sample_rate": SAMPLE_RATE,
            "$process_person_profile": False,
            "$lib": "posthog-python",
        },
    }


def send(payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        POSTHOG_HOST,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT):
            pass
    except Exception:
        pass


def emit(event_type: str, properties: dict | None = None) -> None:
    if not is_enabled():
        return
    send(build_posthog_payload(f"plugin.{event_type}", properties))


def main() -> int:
    if not is_enabled():
        return 0
    if len(sys.argv) < 2:
        return 1

    event_type = sys.argv[1]
    properties: dict = {}

    for arg in sys.argv[2:]:
        if arg.startswith("--memory_count="):
            try:
                properties["memory_count"] = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg.startswith("--categories_count="):
            try:
                properties["categories_count"] = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg == "--error_detected":
            properties["error_detected"] = True
        elif arg == "--file_paths_detected":
            properties["file_paths_detected"] = True
        elif arg.startswith("--source="):
            properties["source_detail"] = arg.split("=", 1)[1]
        elif arg.startswith("--tool="):
            properties["tool"] = arg.split("=", 1)[1]
        elif arg.startswith("--files_count="):
            try:
                properties["files_count"] = int(arg.split("=", 1)[1])
            except ValueError:
                pass

    emit(event_type, properties)
    return 0


if __name__ == "__main__":
    sys.exit(main())
