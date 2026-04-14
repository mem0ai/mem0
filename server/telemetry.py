"""Opt-in anonymous telemetry. Sends a single `onboarding_completed` event per install.

Disabled by default. Enable with `MEM0_TELEMETRY=true`. Fires to the same PostHog
project the mem0 OSS library uses. No PII — only the signup source, email domain,
server version, and a randomly generated install UUID.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import mem0

PROJECT_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX"
HOST = "https://us.i.posthog.com"

ENABLED = os.environ.get("MEM0_TELEMETRY", "").lower() in {"1", "true", "yes", "on"}
STATE_PATH = Path(os.environ.get("MEM0_TELEMETRY_STATE_PATH", "/app/history/telemetry.json"))

_lock = Lock()
_client: Any = None


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state))
    except OSError:
        logging.exception("telemetry: failed to persist state")


def _install_id(state: dict[str, Any]) -> str:
    install_id = state.get("install_id")
    if not install_id:
        install_id = str(uuid.uuid4())
        state["install_id"] = install_id
        _save_state(state)
    return install_id


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from posthog import Posthog
    except ImportError:
        logging.warning("telemetry: posthog package not installed; disabling")
        return None
    _client = Posthog(project_api_key=PROJECT_API_KEY, host=HOST, disable_geoip=True)
    return _client


def log_status() -> None:
    if ENABLED:
        logging.info("telemetry: enabled. Set MEM0_TELEMETRY=false to disable.")


def capture_onboarding_completed(email: str, source: str) -> None:
    if not ENABLED:
        return

    with _lock:
        state = _load_state()
        if state.get("onboarding_sent_at"):
            return

        client = _get_client()
        if client is None:
            return

        try:
            client.capture(
                distinct_id=_install_id(state),
                event="onboarding_completed",
                properties={
                    "source": source,
                    "email_domain": email.rsplit("@", 1)[-1].lower() if "@" in email else "unknown",
                    "server_version": mem0.__version__,
                },
            )
            state["onboarding_sent_at"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)
        except Exception:
            logging.exception("telemetry: failed to send onboarding event")
