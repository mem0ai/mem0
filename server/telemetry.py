"""Anonymous telemetry. Sends at most two events per install:

- `admin_registered` — fires when the first admin account is created (wizard or API).
- `onboarding_completed` — fires when the setup wizard reaches its final success state
  (so dashboard installs emit both; API-only installs emit only the first).

Enabled by default (matching the mem0 OSS library). Opt out with `MEM0_TELEMETRY=false`.
Fires to the same PostHog project the library uses. Shared properties: email domain,
server version, and a randomly generated install UUID. `onboarding_completed` also
carries the operator's freeform use-case string.
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

ENABLED = os.environ.get("MEM0_TELEMETRY", "true").lower() not in {"0", "false", "no", "off"}
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
        logging.info("telemetry: anonymous telemetry is enabled. Set MEM0_TELEMETRY=false to disable.")


def _capture_once(email: str, event: str, state_key: str, extra: dict[str, Any] | None = None) -> None:
    if not ENABLED:
        return

    with _lock:
        state = _load_state()
        if state.get(state_key):
            return

        client = _get_client()
        if client is None:
            return

        try:
            client.capture(
                distinct_id=_install_id(state),
                event=event,
                properties={
                    "email_domain": email.rsplit("@", 1)[-1].lower() if "@" in email else "unknown",
                    "server_version": mem0.__version__,
                    **(extra or {}),
                },
            )
            state[state_key] = datetime.now(timezone.utc).isoformat()
            _save_state(state)
        except Exception:
            logging.exception("telemetry: failed to send %s event", event)


def capture_admin_registered(email: str) -> None:
    _capture_once(email, "admin_registered", "admin_registered_sent_at")


def capture_onboarding_completed(email: str, use_case: str) -> None:
    _capture_once(email, "onboarding_completed", "onboarding_sent_at", {"use_case": use_case})
